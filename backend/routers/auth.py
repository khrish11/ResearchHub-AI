from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from urllib.parse import urlencode, urlparse
from pydantic import BaseModel
import os
import logging
import json
import base64
import httpx
from email_service import (
    generate_verification_token,
    get_verification_token_expiry,
    send_verification_email,
    send_password_reset_email,
    verify_email_token
)
from database import get_db
from models import User, Workspace, Paper, Chat, SearchHistory, UserSessionState, WorkspaceDocument

router = APIRouter(prefix="/auth", tags=["auth"])

APP_ENV = (os.getenv("APP_ENV") or "production").strip().lower()
SECRET_KEY = os.getenv("SECRET_KEY") or "secret"
if APP_ENV != "development" and SECRET_KEY == "secret":
    # In production, main.py enforces a proper SECRET_KEY. This warning is only relevant to development.
    logging.warning("SECRET_KEY not set; using a development fallback. Set SECRET_KEY in backend/.env.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
BACKEND_URL = (os.getenv("BACKEND_URL") or "http://localhost:8000").rstrip("/")
FRONTEND_URL = (os.getenv("FRONTEND_URL") or "http://localhost:5173").rstrip("/")
EMAIL_VERIFICATION_REQUIRED = (
    os.getenv("REQUIRE_EMAIL_VERIFICATION", "1" if APP_ENV == "production" else "0")
    .strip()
    .lower()
    in {"1", "true", "yes"}
)
GOOGLE_REDIRECT_URI = (
    os.getenv("GOOGLE_REDIRECT_URI") or f"{BACKEND_URL}/auth/google/callback"
).rstrip("/")
GOOGLE_OAUTH_TIMEOUT = httpx.Timeout(12.0, connect=5.0)

# Default to a portable hashing scheme. Bcrypt can be enabled explicitly
# by setting the USE_BCRYPT environment variable (and ensuring the system
# has a compatible `bcrypt` package). This avoids import-time failures on
# systems where bcrypt isn't usable.
if os.getenv("USE_BCRYPT", "0") in {"1", "true", "True"}:
    # Probe bcrypt at startup by attempting a quick hash using a temporary
    # CryptContext. If bcrypt fails for any reason, fall back to pbkdf2_sha256.
    try:
        tmp = CryptContext(schemes=["bcrypt"], deprecated="auto")
        try:
            # short test hash to ensure the backend behaves as expected
            tmp.hash("test-short")
            pwd_context = CryptContext(schemes=["bcrypt", "pbkdf2_sha256"], deprecated="auto")
        except Exception:
            pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    except Exception:
        pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
else:
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def _parse_developer_emails() -> set[str]:
    raw = os.getenv("DEVELOPER_EMAILS", "")
    values = [item.strip().lower() for item in raw.split(",") if item.strip()]
    return set(values)


def is_developer_email(email: Optional[str]) -> bool:
    if not email:
        return False
    return email.strip().lower() in _parse_developer_emails()


def _iso_utc(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_email(value: Optional[str]) -> str:
    return str(value or "").strip().lower()


def _merge_duplicate_users_for_email(db: Session, normalized_email: str) -> Optional[User]:
    if not normalized_email:
        return None

    users = (
        db.query(User)
        .filter(
            or_(
                func.lower(func.trim(User.email)) == normalized_email,
                func.lower(func.trim(func.coalesce(User.google_email, ""))) == normalized_email,
            )
        )
        .order_by(User.id.asc())
        .all()
    )
    if not users:
        return None
    if len(users) == 1:
        user = users[0]
        if _normalize_email(user.email) != normalized_email:
            user.email = normalized_email
        if user.google_email and _normalize_email(user.google_email) != normalized_email:
            user.google_email = normalized_email
        if db.is_modified(user):
            db.commit()
            db.refresh(user)
        return user

    def _score(candidate: User) -> Tuple[int, int, int, int]:
        workspace_count = (
            db.query(func.count(Workspace.id))
            .filter(Workspace.user_id == candidate.id)
            .scalar()
            or 0
        )
        paper_count = (
            db.query(func.count(Paper.id))
            .join(Workspace, Paper.workspace_id == Workspace.id)
            .filter(Workspace.user_id == candidate.id)
            .scalar()
            or 0
        )
        search_count = (
            db.query(func.count(SearchHistory.id))
            .filter(SearchHistory.user_id == candidate.id)
            .scalar()
            or 0
        )
        doc_count = (
            db.query(func.count(WorkspaceDocument.id))
            .filter(WorkspaceDocument.user_id == candidate.id)
            .scalar()
            or 0
        )
        auth_score = int(bool(candidate.google_id)) + int(bool(candidate.hashed_password))
        # Higher score wins; for tie use smaller id.
        return int(paper_count), int(workspace_count), int(search_count + doc_count), int(auth_score), -int(candidate.id)

    primary = sorted(users, key=_score, reverse=True)[0]
    primary.email = normalized_email
    if primary.google_email:
        primary.google_email = normalized_email

    for other in users:
        if other.id == primary.id:
            continue

        db.query(Workspace).filter(Workspace.user_id == other.id).update(
            {Workspace.user_id: primary.id}, synchronize_session=False
        )
        db.query(SearchHistory).filter(SearchHistory.user_id == other.id).update(
            {SearchHistory.user_id: primary.id}, synchronize_session=False
        )
        db.query(WorkspaceDocument).filter(WorkspaceDocument.user_id == other.id).update(
            {WorkspaceDocument.user_id: primary.id}, synchronize_session=False
        )

        other_state = db.query(UserSessionState).filter(UserSessionState.user_id == other.id).first()
        primary_state = db.query(UserSessionState).filter(UserSessionState.user_id == primary.id).first()
        if other_state and not primary_state:
            other_state.user_id = primary.id
        elif other_state and primary_state:
            epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
            primary_updated = primary_state.updated_at or epoch
            other_updated = other_state.updated_at or epoch
            if primary_updated.tzinfo is None:
                primary_updated = primary_updated.replace(tzinfo=timezone.utc)
            if other_updated.tzinfo is None:
                other_updated = other_updated.replace(tzinfo=timezone.utc)
            if other_updated > primary_updated:
                primary_state.page_path = other_state.page_path
                primary_state.workspace_id = other_state.workspace_id
                primary_state.last_query = other_state.last_query
                primary_state.draft_text = other_state.draft_text
                primary_state.extra_json = other_state.extra_json
                primary_state.updated_at = other_state.updated_at
            db.delete(other_state)

        if not primary.google_id and other.google_id:
            primary.google_id = other.google_id
            primary.google_email = _normalize_email(other.google_email) or normalized_email
            primary.profile_pic = primary.profile_pic or other.profile_pic
        if not primary.hashed_password and other.hashed_password:
            primary.hashed_password = other.hashed_password
        primary.is_verified = bool(primary.is_verified or other.is_verified)
        primary.is_active = bool(primary.is_active or other.is_active)
        if not primary.name and other.name:
            primary.name = other.name

        db.delete(other)

    db.commit()
    db.refresh(primary)
    return primary

class UserCreate(BaseModel):
    email: str
    password: str
    name: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)


def _resolve_google_redirect_uri(request: Optional[Request] = None) -> str:
    """Use configured redirect URI to keep Google OAuth callback deterministic."""
    return GOOGLE_REDIRECT_URI


def _is_local_host(hostname: Optional[str]) -> bool:
    host = (hostname or "").strip().lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def _resolve_frontend_redirect(frontend_redirect: Optional[str]) -> str:
    """Allow redirects only for configured frontend origin, with localhost flexibility."""
    if not frontend_redirect:
        return FRONTEND_URL

    try:
        parsed = urlparse(frontend_redirect)
        configured = urlparse(FRONTEND_URL)
        if parsed.scheme not in {"http", "https"}:
            return FRONTEND_URL
        parsed_host = (parsed.hostname or "").lower()
        configured_host = (configured.hostname or "").lower()
        same_host = bool(parsed_host and configured_host and parsed_host == configured_host)
        local_host_pair = _is_local_host(parsed_host) and _is_local_host(configured_host)
        if not (same_host or local_host_pair):
            return FRONTEND_URL
        parsed_port = parsed.port or (443 if parsed.scheme == "https" else 80)
        configured_port = configured.port or (443 if configured.scheme == "https" else 80)
        # In local development users often switch between localhost ports
        # (e.g., :5173, :3000, or reverse-proxy path on :80).
        if not local_host_pair and parsed_port != configured_port:
            return FRONTEND_URL
        if parsed.path and parsed.path != "/":
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return FRONTEND_URL


def _decode_oauth_state(raw_state: Optional[str]) -> dict:
    if not raw_state:
        return {}
    try:
        padded = raw_state + "=" * (-len(raw_state) % 4)
        data = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        parsed = json.loads(data)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return {}


def _encode_oauth_state(payload: dict) -> str:
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("utf-8").rstrip("=")


def _redirect_with_query(base_url: str, params: dict) -> RedirectResponse:
    query = urlencode(params)
    sep = "&" if "?" in base_url else "?"
    return RedirectResponse(f"{base_url}{sep}{query}")


def _google_error_redirect(message: str, frontend_redirect: Optional[str] = None) -> RedirectResponse:
    target = _resolve_frontend_redirect(frontend_redirect)
    query = urlencode({"error": message})
    return RedirectResponse(f"{target}/login?{query}")


def _friendly_google_oauth_error(exc: Exception) -> str:
    details = []
    for attr in ("error", "description", "message"):
        value = getattr(exc, attr, None)
        if value:
            details.append(str(value))
    details.append(str(exc))
    raw = " ".join(details).lower()

    if "redirect_uri_mismatch" in raw or "redirect uri mismatch" in raw:
        return f"Google OAuth redirect URI mismatch. Use {GOOGLE_REDIRECT_URI} in Google Cloud OAuth settings."
    if "invalid_client" in raw:
        return "Google OAuth client is invalid. Check GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
    if "invalid_grant" in raw:
        return "Google OAuth grant invalid. Retry sign-in and ensure redirect URI exactly matches Google Console."
    if "timeout" in raw or "timed out" in raw:
        return "Google sign-in timed out. Please retry."
    if "access_denied" in raw:
        return "Google sign-in was denied."

    if os.getenv("APP_ENV", "production") == "development":
        snippet = " ".join(str(exc).split())[:180]
        return (
            "Google sign-in failed. Verify Google OAuth credentials and redirect URI, then try again. "
            f"Details: {snippet}"
        )
    return "Google sign-in failed. Verify Google OAuth credentials and redirect URI, then try again."

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    normalized_email = _normalize_email(email)
    user = _merge_duplicate_users_for_email(db, normalized_email)
    if user is None:
        raise credentials_exception
    return user

@router.post("/register")
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    normalized_email = _normalize_email(user_data.email)
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Email is required")
    # Check if user already exists
    existing_user = _merge_duplicate_users_for_email(db, normalized_email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user
    hashed_password = get_password_hash(user_data.password)
    verification_token = generate_verification_token() if EMAIL_VERIFICATION_REQUIRED else None
    verification_expires = get_verification_token_expiry() if EMAIL_VERIFICATION_REQUIRED else None

    user = User(
        email=normalized_email,
        hashed_password=hashed_password,
        name=user_data.name,
        is_active=True,
        is_verified=not EMAIL_VERIFICATION_REQUIRED,
        verification_token=verification_token,
        verification_token_expires=verification_expires
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if not EMAIL_VERIFICATION_REQUIRED:
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
        return {
            "message": "User registered successfully.",
            "access_token": access_token,
            "token_type": "bearer",
        }

    # Send verification email when verification is required.
    if verification_token:
        try:
            await send_verification_email(user.email, verification_token, user.name)
        except Exception as e:
            logging.error(f"Failed to send verification email: {e}")
            # Do not fail registration if email delivery fails.

    return {"message": "User registered successfully. Please check your email to verify your account."}

@router.post("/verify-email")
async def verify_email(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.verification_token == token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification token")

    if not user.verification_token_expires or user.verification_token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Verification token has expired")

    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    db.commit()
    db.refresh(user)

    return {"message": "Email verified successfully"}

@router.post("/resend-verification-email")
async def resend_verification_email(email: str, db: Session = Depends(get_db)):
    normalized_email = _normalize_email(email)
    user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    if user.is_verified:
        raise HTTPException(status_code=400, detail="Email is already verified")

    verification_token = generate_verification_token()
    verification_expires = get_verification_token_expiry()

    user.verification_token = verification_token
    user.verification_token_expires = verification_expires
    db.commit()
    db.refresh(user)

    try:
        await send_verification_email(user.email, verification_token, user.name)
    except Exception as e:
        logging.error(f"Failed to send verification email: {e}")
        # Don't fail registration if email fails, but log it

    return {"message": "Verification email resent successfully"}

@router.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    username = (form_data.username or "").strip().lower()
    user = _merge_duplicate_users_for_email(db, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.google_id and not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account uses Google sign-in. Please use Sign in with Google.",
        )
    try:
        password_ok = bool(user.hashed_password) and verify_password(form_data.password, user.hashed_password)
    except Exception:
        password_ok = False
    if not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is deactivated",
        )
    if EMAIL_VERIFICATION_REQUIRED and not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your email and verify your account.",
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

class UserOut(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    google_id: Optional[str] = None
    google_email: Optional[str] = None
    profile_pic: Optional[str] = None
    is_verified: bool = False
    is_active: bool = True
    is_developer: bool = False

class ProfileUpdate(BaseModel):
    name: Optional[str] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class DeleteAccountRequest(BaseModel):
    confirm_email: str
    password: Optional[str] = None

@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id, 
        "email": current_user.email,
        "name": current_user.name,
        "google_id": current_user.google_id,
        "google_email": current_user.google_email,
        "profile_pic": current_user.profile_pic,
        "is_verified": current_user.is_verified,
        "is_active": current_user.is_active,
        "is_developer": is_developer_email(current_user.email),
    }


@router.get("/me/overview")
async def get_me_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace_count = (
        db.query(func.count(Workspace.id))
        .filter(Workspace.user_id == current_user.id)
        .scalar()
        or 0
    )
    paper_count = (
        db.query(func.count(Paper.id))
        .join(Workspace, Paper.workspace_id == Workspace.id)
        .filter(Workspace.user_id == current_user.id)
        .scalar()
        or 0
    )
    chat_count = (
        db.query(func.count(Chat.id))
        .join(Workspace, Chat.workspace_id == Workspace.id)
        .filter(Workspace.user_id == current_user.id)
        .scalar()
        or 0
    )
    search_count = (
        db.query(func.count(SearchHistory.id))
        .filter(SearchHistory.user_id == current_user.id)
        .scalar()
        or 0
    )
    doc_count = (
        db.query(func.count(WorkspaceDocument.id))
        .filter(WorkspaceDocument.user_id == current_user.id)
        .scalar()
        or 0
    )

    recent_search_rows = (
        db.query(SearchHistory)
        .filter(SearchHistory.user_id == current_user.id)
        .order_by(SearchHistory.created_at.desc())
        .limit(8)
        .all()
    )
    recent_workspace_rows = (
        db.query(Workspace)
        .filter(Workspace.user_id == current_user.id)
        .order_by(Workspace.created_at.desc())
        .limit(6)
        .all()
    )
    state = (
        db.query(UserSessionState)
        .filter(UserSessionState.user_id == current_user.id)
        .first()
    )

    now = datetime.now(timezone.utc)
    created_at = current_user.created_at
    if created_at and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    account_age_days = (
        max(0, int((now - created_at).total_seconds() // 86400))
        if created_at
        else 0
    )

    recent_searches = [
        {
            "id": row.id,
            "query": row.query,
            "source": row.source,
            "result_count": int(row.result_count or 0),
            "created_at": _iso_utc(row.created_at),
        }
        for row in recent_search_rows
    ]

    recent_workspaces = [
        {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "created_at": _iso_utc(row.created_at),
        }
        for row in recent_workspace_rows
    ]

    return {
        "account": {
            "created_at": _iso_utc(created_at),
            "updated_at": _iso_utc(current_user.updated_at),
            "account_age_days": account_age_days,
            "google_linked": bool(current_user.google_id),
            "is_verified": bool(current_user.is_verified),
        },
        "counts": {
            "workspaces": int(workspace_count),
            "papers": int(paper_count),
            "chats": int(chat_count),
            "searches": int(search_count),
            "documents": int(doc_count),
        },
        "recent_searches": recent_searches,
        "recent_workspaces": recent_workspaces,
        "resume": {
            "page_path": (state.page_path if state else "/home"),
            "workspace_id": (state.workspace_id if state else None),
            "last_query": (state.last_query if state else None),
            "updated_at": _iso_utc(state.updated_at) if state else None,
        },
    }


@router.get('/google/login')
async def google_login(request: Request):
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    if not client_id or not os.getenv("GOOGLE_CLIENT_SECRET"):
        raise HTTPException(status_code=500, detail="Google OAuth is not configured")

    redirect_uri = _resolve_google_redirect_uri(request)
    frontend_redirect = _resolve_frontend_redirect(request.query_params.get("frontend_redirect"))
    state = _encode_oauth_state({"frontend_redirect": frontend_redirect})
    authorization_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "include_granted_scopes": "true",
            "access_type": "online",
        }
    )
    return RedirectResponse(authorization_url)

@router.get('/google/status')
async def google_status():
    configured = bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    client_id_hint = f"{client_id[:14]}..." if client_id else None
    return {
        "configured": configured,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "frontend_url": FRONTEND_URL,
        "backend_url": BACKEND_URL,
        "client_id_hint": client_id_hint,
    }

@router.get('/google/callback')
async def google_callback(request: Request, db: Session = Depends(get_db)):
    state_payload = _decode_oauth_state(request.query_params.get("state"))
    frontend_redirect = _resolve_frontend_redirect(state_payload.get("frontend_redirect"))

    if request.query_params.get("error"):
        error_description = request.query_params.get("error_description")
        message = "Google sign-in was cancelled or denied."
        if error_description:
            message = f"Google sign-in failed: {error_description}"
        return _google_error_redirect(message, frontend_redirect)

    code = request.query_params.get("code")
    if not code:
        return _google_error_redirect("Missing authorization code from Google.", frontend_redirect)

    redirect_uri = _resolve_google_redirect_uri(request)
    try:
        async with httpx.AsyncClient(timeout=GOOGLE_OAUTH_TIMEOUT) as client:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                    "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
            token_resp.raise_for_status()
            token_payload = token_resp.json()
            access_token = token_payload.get("access_token") if isinstance(token_payload, dict) else None
            if not access_token:
                raise RuntimeError("Google OAuth token response missing access_token")

            userinfo_resp = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_resp.raise_for_status()
            user_info = userinfo_resp.json()
        google_id = user_info.get('sub')
        email = _normalize_email(user_info.get('email'))
        if not google_id or not email:
            logging.warning("Google userinfo missing required fields: %s", user_info)
            return _google_error_redirect(
                "Google account info was incomplete. Please try again.",
                frontend_redirect,
            )
        if user_info.get("email_verified") is False:
            return _google_error_redirect(
                "Google email is not verified. Use a verified account.",
                frontend_redirect,
            )
        name = user_info.get('name')
        picture = user_info.get('picture')
    except Exception as exc:
        logging.exception("Google OAuth callback failed")
        return _google_error_redirect(
            _friendly_google_oauth_error(exc),
            frontend_redirect,
        )

    # Reconcile fragmented accounts by email first (handles legacy rows with
    # mixed casing/spacing or rows that only had google_email set).
    merged_email_user = _merge_duplicate_users_for_email(db, email)
    user_by_google = db.query(User).filter(User.google_id == google_id).first()

    if user_by_google and merged_email_user and user_by_google.id != merged_email_user.id:
        # Keep the richer merged-email account as primary and move Google identity to it.
        merged_email_user.google_id = google_id
        merged_email_user.google_email = email
        merged_email_user.email = email
        merged_email_user.name = merged_email_user.name or name
        merged_email_user.profile_pic = merged_email_user.profile_pic or picture
        merged_email_user.is_verified = True

        db.query(Workspace).filter(Workspace.user_id == user_by_google.id).update(
            {Workspace.user_id: merged_email_user.id}, synchronize_session=False
        )
        db.query(SearchHistory).filter(SearchHistory.user_id == user_by_google.id).update(
            {SearchHistory.user_id: merged_email_user.id}, synchronize_session=False
        )
        db.query(WorkspaceDocument).filter(WorkspaceDocument.user_id == user_by_google.id).update(
            {WorkspaceDocument.user_id: merged_email_user.id}, synchronize_session=False
        )

        secondary_state = db.query(UserSessionState).filter(UserSessionState.user_id == user_by_google.id).first()
        primary_state = db.query(UserSessionState).filter(UserSessionState.user_id == merged_email_user.id).first()
        if secondary_state and not primary_state:
            secondary_state.user_id = merged_email_user.id
        elif secondary_state and primary_state:
            epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
            primary_updated = primary_state.updated_at or epoch
            secondary_updated = secondary_state.updated_at or epoch
            if primary_updated.tzinfo is None:
                primary_updated = primary_updated.replace(tzinfo=timezone.utc)
            if secondary_updated.tzinfo is None:
                secondary_updated = secondary_updated.replace(tzinfo=timezone.utc)
            if secondary_updated > primary_updated:
                primary_state.page_path = secondary_state.page_path
                primary_state.workspace_id = secondary_state.workspace_id
                primary_state.last_query = secondary_state.last_query
                primary_state.draft_text = secondary_state.draft_text
                primary_state.extra_json = secondary_state.extra_json
                primary_state.updated_at = secondary_state.updated_at
            db.delete(secondary_state)
        db.delete(user_by_google)
        user = merged_email_user
    elif user_by_google:
        user = user_by_google
    elif merged_email_user:
        user = merged_email_user
        user.google_id = google_id
        user.google_email = email
        user.email = email
    else:
        user = User(
            email=email,
            google_id=google_id,
            google_email=email,
            name=name,
            profile_pic=picture,
            is_verified=True,
        )
        db.add(user)

    user.email = email
    user.google_email = email
    user.google_id = google_id
    user.name = name or user.name
    user.profile_pic = picture or user.profile_pic
    user.is_verified = True
    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError:
        db.rollback()
        logging.exception("Failed to persist Google user during callback")
        return _google_error_redirect(
            "Account linking failed. Try signing in again.",
            frontend_redirect,
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    
    return _redirect_with_query(frontend_redirect, {"token": access_token})

@router.patch("/me")
async def update_profile(
    profile_data: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if profile_data.name is not None:
        current_user.name = profile_data.name
    db.commit()
    db.refresh(current_user)
    return {"message": "Profile updated successfully"}

@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Only allow password change for non-Google users
    if current_user.google_id:
        raise HTTPException(status_code=400, detail="Password change not available for Google-linked accounts")
    
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    current_user.hashed_password = get_password_hash(password_data.new_password)
    db.commit()
    return {"message": "Password changed successfully"}

@router.delete("/me")
async def delete_account(
    delete_data: DeleteAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if delete_data.confirm_email.strip().lower() != current_user.email.lower():
        raise HTTPException(status_code=400, detail="Confirmation email does not match your account")

    if not current_user.google_id:
        if not delete_data.password:
            raise HTTPException(status_code=400, detail="Password is required to delete account")
        if not verify_password(delete_data.password, current_user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

    workspace_ids = [
        workspace_id
        for (workspace_id,) in db.query(Workspace.id).filter(Workspace.user_id == current_user.id).all()
    ]
    if workspace_ids:
        db.query(Chat).filter(Chat.workspace_id.in_(workspace_ids)).delete(synchronize_session=False)
        db.query(Paper).filter(Paper.workspace_id.in_(workspace_ids)).delete(synchronize_session=False)
        db.query(WorkspaceDocument).filter(WorkspaceDocument.workspace_id.in_(workspace_ids)).delete(synchronize_session=False)
        db.query(Workspace).filter(Workspace.id.in_(workspace_ids)).delete(synchronize_session=False)
    db.query(WorkspaceDocument).filter(WorkspaceDocument.user_id == current_user.id).delete(synchronize_session=False)
    db.query(SearchHistory).filter(SearchHistory.user_id == current_user.id).delete(synchronize_session=False)
    db.query(UserSessionState).filter(UserSessionState.user_id == current_user.id).delete(synchronize_session=False)

    db.delete(current_user)
    db.commit()
    return {"message": "Account deleted successfully"}
