from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode, urlparse
from pydantic import BaseModel
import os
import logging
import json
import base64
import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from database import get_db
from models import User, Workspace, Paper, Chat

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = os.getenv("SECRET_KEY") or "secret"
if os.getenv("APP_ENV", "production") != "development" and SECRET_KEY == "secret":
    # In production, main.py enforces a proper SECRET_KEY. This warning is only relevant to development.
    logging.warning("SECRET_KEY not set; using a development fallback. Set SECRET_KEY in backend/.env.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
BACKEND_URL = (os.getenv("BACKEND_URL") or "http://localhost:8000").rstrip("/")
FRONTEND_URL = (os.getenv("FRONTEND_URL") or "http://localhost:5173").rstrip("/")
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

class UserCreate(BaseModel):
    email: str
    password: str

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


def _resolve_frontend_redirect(frontend_redirect: Optional[str]) -> str:
    """Allow redirects only when origin matches configured FRONTEND_URL."""
    if not frontend_redirect:
        return FRONTEND_URL

    try:
        parsed = urlparse(frontend_redirect)
        configured = urlparse(FRONTEND_URL)
        if parsed.scheme not in {"http", "https"}:
            return FRONTEND_URL
        if not parsed.hostname or parsed.hostname != configured.hostname:
            return FRONTEND_URL
        parsed_port = parsed.port or (443 if parsed.scheme == "https" else 80)
        configured_port = configured.port or (443 if configured.scheme == "https" else 80)
        if parsed_port != configured_port:
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
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

@router.post("/register", response_model=Token)
def register(user: UserCreate, db: Session = Depends(get_db)):
    email = user.email.strip().lower()
    db_user = db.query(User).filter(func.lower(User.email) == email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user.password)
    new_user = User(email=email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Issue a token consistent with /auth/token lifetime
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": new_user.email}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    username = (form_data.username or "").strip().lower()
    user = db.query(User).filter(func.lower(User.email) == username).first()
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
        "profile_pic": current_user.profile_pic
    }

@router.get('/google/login')
async def google_login(request: Request):
    if not os.getenv("GOOGLE_CLIENT_ID") or not os.getenv("GOOGLE_CLIENT_SECRET"):
        raise HTTPException(status_code=500, detail="Google OAuth is not configured")

    redirect_uri = _resolve_google_redirect_uri(request)
    frontend_redirect = _resolve_frontend_redirect(request.query_params.get("frontend_redirect"))
    state = _encode_oauth_state({"frontend_redirect": frontend_redirect})
    async with AsyncOAuth2Client(
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        redirect_uri=redirect_uri,
        token_endpoint_auth_method='client_secret_post',
        timeout=GOOGLE_OAUTH_TIMEOUT,
    ) as client:
        authorization_url, _ = client.create_authorization_url(
            'https://accounts.google.com/o/oauth2/v2/auth',
            scope='openid email profile',
            state=state
        )
    return RedirectResponse(authorization_url)

@router.get('/google/status')
async def google_status():
    configured = bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))
    return {"configured": configured}

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
        async with AsyncOAuth2Client(
            client_id=os.getenv('GOOGLE_CLIENT_ID'),
            client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
            redirect_uri=redirect_uri,
            token_endpoint_auth_method='client_secret_post',
            timeout=GOOGLE_OAUTH_TIMEOUT,
        ) as client:
            token = await client.fetch_token(
                'https://oauth2.googleapis.com/token',
                code=code,
                grant_type='authorization_code',
                redirect_uri=redirect_uri,
                client_id=os.getenv('GOOGLE_CLIENT_ID'),
                client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
            )
            access_token = token.get("access_token") if isinstance(token, dict) else None
            if not access_token:
                raise RuntimeError("Google OAuth token response missing access_token")

            userinfo_resp = await client.get(
                'https://openidconnect.googleapis.com/v1/userinfo',
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_resp.raise_for_status()
            user_info = userinfo_resp.json()
        google_id = user_info.get('sub')
        email = user_info.get('email')
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
    
    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        existing_user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
        if existing_user:
            existing_user.google_id = google_id
            existing_user.google_email = email
            existing_user.name = name
            existing_user.profile_pic = picture
            user = existing_user
        else:
            user = User(
                email=email,
                google_id=google_id,
                google_email=email,
                name=name,
                profile_pic=picture
            )
            db.add(user)
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
        db.query(Workspace).filter(Workspace.id.in_(workspace_ids)).delete(synchronize_session=False)

    db.delete(current_user)
    db.commit()
    return {"message": "Account deleted successfully"}
