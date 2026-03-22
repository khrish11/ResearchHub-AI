from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext
import jwt
from jwt import InvalidTokenError
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Optional, Tuple
from urllib.parse import quote, urlencode, urlparse
from pydantic import BaseModel
import os
import logging
import httpx
import re
import time
import hashlib
import secrets
from email_service import (
    generate_verification_token,
    get_verification_token_expiry,
    send_verification_email,
    send_password_reset_email,
)
from repositories import ResearchRepository, get_research_repository
from repositories.research import User
from utils.firebase_admin_client import (
    firebase_admin_is_configured,
    firebase_sign_in_provider,
    verify_firebase_id_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

APP_ENV = (os.getenv("APP_ENV") or "production").strip().lower()
SECRET_KEY = os.getenv("SECRET_KEY") or "secret"
if APP_ENV != "development" and SECRET_KEY == "secret":
    # In production, main.py enforces a proper SECRET_KEY. This warning is only relevant to development.
    logging.warning(
        "SECRET_KEY not set; using a development fallback. Set SECRET_KEY in backend/.env."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 14
BACKEND_URL = (os.getenv("BACKEND_URL") or "http://localhost:8010").rstrip("/")
FRONTEND_URL = (os.getenv("FRONTEND_URL") or "http://localhost:5173").rstrip("/")
EMAIL_VERIFICATION_REQUIRED = os.getenv(
    "REQUIRE_EMAIL_VERIFICATION", "1" if APP_ENV == "production" else "0"
).strip().lower() in {"1", "true", "yes"}
GOOGLE_REDIRECT_URI = (
    os.getenv("GOOGLE_REDIRECT_URI") or f"{BACKEND_URL}/auth/google/callback"
).rstrip("/")
GOOGLE_OAUTH_TIMEOUT = httpx.Timeout(12.0, connect=5.0)
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
GOOGLE_OAUTH_STATE_COOKIE_NAME = "researchhub_google_oauth_state"
GOOGLE_OAUTH_STATE_TTL_SECONDS = 10 * 60
OAUTH_HANDOFF_TTL_SECONDS = 2 * 60
ACCESS_TOKEN_COOKIE_NAME = "researchhub_access_token"
REFRESH_TOKEN_COOKIE_NAME = "researchhub_refresh_token"
COOKIE_SAMESITE = (os.getenv("AUTH_COOKIE_SAMESITE") or "lax").strip().lower() or "lax"
COOKIE_DOMAIN = (os.getenv("AUTH_COOKIE_DOMAIN") or "").strip() or None
DEFAULT_AUTH_COOKIE_SECURE = "1" if APP_ENV in {"production", "staging"} else "0"
COOKIE_SECURE = os.getenv(
    "AUTH_COOKIE_SECURE", DEFAULT_AUTH_COOKIE_SECURE
).strip().lower() in {"1", "true", "yes"}
_INMEM_REFRESH_STORE: dict[str, dict[str, Any]] = {}
_INMEM_REFRESH_LOCK = Lock()


# ---------------------------------------------------------------------------
# Firebase Firestore refresh-token helpers
# ---------------------------------------------------------------------------


def _firebase_firestore_db():
    """Return a Firestore client, or None if Firebase is not configured."""
    try:
        from utils.firebase_admin_client import get_firebase_admin_app
        import firebase_admin.firestore as _fs

        return _fs.client(app=get_firebase_admin_app())
    except Exception:
        return None


def _firebase_persist_refresh_token(
    user_id: int, token_hash: str, expires_at: datetime
) -> None:
    db = _firebase_firestore_db()
    if db is None:
        with _INMEM_REFRESH_LOCK:
            _INMEM_REFRESH_STORE[token_hash] = {
                "user_id": int(user_id),
                "expires_at": _normalize_dt(expires_at),
                "revoked_at": None,
                "replaced_by_hash": None,
            }
        return
    db.collection("refresh_sessions").document(token_hash).set(
        {
            "user_id": int(user_id),
            "token_hash": token_hash,
            "expires_at": _normalize_dt(expires_at),
            "revoked_at": None,
            "replaced_by_hash": None,
            "created_at": _now_utc(),
        }
    )


def _firebase_mark_refresh_token_revoked(
    token_hash: str, replaced_by_hash: Optional[str] = None
) -> bool:
    db = _firebase_firestore_db()
    if db is None:
        with _INMEM_REFRESH_LOCK:
            row = _INMEM_REFRESH_STORE.get(token_hash)
            if not row:
                return False
            row["revoked_at"] = _now_utc()
            row["replaced_by_hash"] = replaced_by_hash
        return True
    ref = db.collection("refresh_sessions").document(token_hash)
    doc = ref.get()
    if not doc.exists:
        return False
    ref.update({"revoked_at": _now_utc(), "replaced_by_hash": replaced_by_hash})
    return True


def _firebase_rotate_refresh_token(
    token_hash: str,
) -> Optional[Tuple[int, str, datetime]]:
    db = _firebase_firestore_db()
    if db is None:
        with _INMEM_REFRESH_LOCK:
            row = _INMEM_REFRESH_STORE.get(token_hash)
            if not row:
                return None
            if row.get("revoked_at") is not None:
                return None
            now = _now_utc()
            if _normalize_dt(row.get("expires_at")) <= now:
                row["revoked_at"] = now
                return None
            user_id = int(row["user_id"])
            new_raw = secrets.token_urlsafe(48)
            new_hash = _hash_refresh_token(new_raw)
            new_expires = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
            row["revoked_at"] = now
            row["replaced_by_hash"] = new_hash
            _INMEM_REFRESH_STORE[new_hash] = {
                "user_id": user_id,
                "expires_at": new_expires,
                "revoked_at": None,
                "replaced_by_hash": None,
            }
            return user_id, new_raw, new_expires

    ref = db.collection("refresh_sessions").document(token_hash)
    doc = ref.get()
    if not doc.exists:
        return None
    row = doc.to_dict() or {}
    if row.get("revoked_at") is not None:
        return None
    now = _now_utc()
    stored_expires = row.get("expires_at")
    if stored_expires is not None:
        if hasattr(stored_expires, "tzinfo") and stored_expires.tzinfo is None:
            stored_expires = stored_expires.replace(tzinfo=timezone.utc)
        if stored_expires <= now:
            ref.update({"revoked_at": now})
            return None
    user_id = int(row.get("user_id", 0))
    new_raw = secrets.token_urlsafe(48)
    new_hash = _hash_refresh_token(new_raw)
    new_expires = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    ref.update({"revoked_at": now, "replaced_by_hash": new_hash})
    db.collection("refresh_sessions").document(new_hash).set(
        {
            "user_id": user_id,
            "token_hash": new_hash,
            "expires_at": new_expires,
            "revoked_at": None,
            "replaced_by_hash": None,
            "created_at": now,
        }
    )
    return user_id, new_raw, new_expires


_PASSWORD_LETTER_RE = re.compile(r"[A-Za-z]")
_PASSWORD_NUMBER_RE = re.compile(r"\d")
_OAUTH_HANDOFF_STORE: dict[str, tuple[float, str]] = {}
_OAUTH_HANDOFF_LOCK = Lock()

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
            pwd_context = CryptContext(
                schemes=["bcrypt", "pbkdf2_sha256"], deprecated="auto"
            )
        except Exception:
            pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    except Exception:
        pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
else:
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)


# ---------------------------------------------------------------------------
# Public JWT helpers (importable by tests and other modules)
# ---------------------------------------------------------------------------


def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    """Create a signed JWT access token.

    Args:
        data: Payload dict; must include ``"sub"`` (subject / email).
        expires_delta: Lifetime override; defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta is not None
        else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT access token.

    Returns:
        The decoded payload dict, or ``None`` on any error (expired,
        malformed, bad signature, etc.).
    """
    if not token:
        return None
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None




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


def _merge_duplicate_users_for_email(
    repo: ResearchRepository, normalized_email: str
) -> Optional[Any]:
    if not normalized_email:
        return None

    users = repo.list_users_for_normalized_email(normalized_email)
    if not users:
        return None
    if len(users) == 1:
        user = users[0]
        if _normalize_email(user.email) != normalized_email:
            user.email = normalized_email
        if (
            user.google_email
            and _normalize_email(user.google_email) != normalized_email
        ):
            user.google_email = normalized_email
        return repo.save(user)

    def _score(candidate: Any) -> Tuple[int, int, int, int, int]:
        workspaces = repo.list_workspaces_for_user(candidate.id)
        workspace_count = len(workspaces)
        paper_count = sum(
            len(repo.list_papers_for_workspace(workspace.id))
            for workspace in workspaces
        )
        search_count = repo.count_search_history_for_user(candidate.id)
        doc_count = repo.count_documents_for_user(candidate.id)
        auth_score = int(bool(candidate.google_id)) + int(
            bool(candidate.hashed_password)
        )
        # Higher score wins; for tie use smaller id.
        return (
            int(paper_count),
            int(workspace_count),
            int(search_count + doc_count),
            int(auth_score),
            -int(candidate.id),
        )

    primary = sorted(users, key=_score, reverse=True)[0]
    primary.email = normalized_email
    if primary.google_email:
        primary.google_email = normalized_email

    for other in users:
        if other.id == primary.id:
            continue
        if not primary.google_id and other.google_id:
            primary.google_id = other.google_id
            primary.google_email = (
                _normalize_email(other.google_email) or normalized_email
            )
            primary.profile_pic = primary.profile_pic or other.profile_pic
        if not primary.hashed_password and other.hashed_password:
            primary.hashed_password = other.hashed_password
        primary.is_verified = bool(primary.is_verified or other.is_verified)
        primary.is_active = bool(primary.is_active or other.is_active)
        if not primary.name and other.name:
            primary.name = other.name

        repo.save(primary)
        repo.merge_user_accounts(primary.id, other.id)

    return repo.save(primary)


class UserCreate(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str


class FirebaseSessionIn(BaseModel):
    id_token: str


class OAuthExchangeIn(BaseModel):
    code: str


class ForgotPasswordIn(BaseModel):
    email: str


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str


PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 60  # 1 hour


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def _validate_password_or_400(password: str) -> str:
    candidate = str(password or "")
    if len(candidate) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.",
        )
    if len(candidate) > MAX_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at most {MAX_PASSWORD_LENGTH} characters long.",
        )
    if candidate.isspace():
        raise HTTPException(
            status_code=400, detail="Password cannot be blank or whitespace only."
        )
    if not _PASSWORD_LETTER_RE.search(candidate) or not _PASSWORD_NUMBER_RE.search(
        candidate
    ):
        raise HTTPException(
            status_code=400,
            detail="Password must include at least one letter and one number.",
        )
    return candidate


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)





def _hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _normalize_dt(value: Optional[datetime]) -> datetime:
    if not value:
        return _now_utc()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _cookie_secure(request: Request) -> bool:
    if COOKIE_SECURE:
        return True
    forwarded = (
        str(request.headers.get("x-forwarded-proto", "")).split(",")[0].strip().lower()
    )
    return request.url.scheme == "https" or forwarded == "https"


def _set_auth_cookies(
    response: Response, request: Request, access_token: str, refresh_token: str
) -> None:
    response.set_cookie(
        ACCESS_TOKEN_COOKIE_NAME,
        access_token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=_cookie_secure(request),
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        path="/",
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE_NAME,
        refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=_cookie_secure(request),
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        path="/",
    )


def _clear_auth_cookies(response: Response, request: Request) -> None:
    response.delete_cookie(ACCESS_TOKEN_COOKIE_NAME, path="/", domain=COOKIE_DOMAIN)
    response.delete_cookie(REFRESH_TOKEN_COOKIE_NAME, path="/", domain=COOKIE_DOMAIN)


def _persist_refresh_token(
    user_id: int, refresh_token: str, expires_at: datetime
) -> None:
    token_hash = _hash_refresh_token(refresh_token)
    _firebase_persist_refresh_token(int(user_id), token_hash, expires_at)


def _create_refresh_token_for_user(user_id: int) -> tuple[str, datetime]:
    raw_refresh = secrets.token_urlsafe(48)
    expires_at = _now_utc() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    _persist_refresh_token(
        user_id=int(user_id), refresh_token=raw_refresh, expires_at=expires_at
    )
    return raw_refresh, expires_at


def _mark_refresh_token_revoked(
    raw_refresh_token: str, replaced_by_hash: Optional[str] = None
) -> bool:
    token_hash = _hash_refresh_token(raw_refresh_token)
    return _firebase_mark_refresh_token_revoked(token_hash, replaced_by_hash)


def _decode_access_token_or_401(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if payload.get("token_type") and payload.get("token_type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def _resolve_access_token(
    request: Request,
    bearer_token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[str]:
    if bearer_token:
        return str(bearer_token).strip()
    cookie_token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    if cookie_token:
        return str(cookie_token).strip()
    return None


def _rotate_refresh_token(
    raw_refresh_token: str,
) -> Optional[tuple[int, str, datetime]]:
    token_hash = _hash_refresh_token(raw_refresh_token)
    return _firebase_rotate_refresh_token(token_hash)


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
        same_host = bool(
            parsed_host and configured_host and parsed_host == configured_host
        )
        local_host_pair = _is_local_host(parsed_host) and _is_local_host(
            configured_host
        )
        if not (same_host or local_host_pair):
            return FRONTEND_URL
        parsed_port = parsed.port or (443 if parsed.scheme == "https" else 80)
        configured_port = configured.port or (
            443 if configured.scheme == "https" else 80
        )
        # In local development users often switch between localhost ports
        # (e.g., :5173, :3000, or reverse-proxy path on :80).
        if not local_host_pair and parsed_port != configured_port:
            return FRONTEND_URL
        if parsed.path and parsed.path != "/":
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return FRONTEND_URL


def _encode_google_oauth_state(frontend_redirect: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "type": "google_oauth_state",
        "frontend_redirect": frontend_redirect,
        "nonce": os.urandom(12).hex(),
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(seconds=GOOGLE_OAUTH_STATE_TTL_SECONDS)).timestamp()
        ),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode_google_oauth_state(raw_state: str) -> dict:
    payload = jwt.decode(raw_state, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != "google_oauth_state":
        raise InvalidTokenError("Unexpected Google OAuth state type.")
    return payload


def _is_https_request(request: Request) -> bool:
    forwarded = (
        str(request.headers.get("x-forwarded-proto", "")).split(",")[0].strip().lower()
    )
    return request.url.scheme == "https" or forwarded == "https"


def _set_google_state_cookie(
    response: RedirectResponse, request: Request, state: str
) -> None:
    response.set_cookie(
        GOOGLE_OAUTH_STATE_COOKIE_NAME,
        state,
        max_age=GOOGLE_OAUTH_STATE_TTL_SECONDS,
        httponly=True,
        secure=_is_https_request(request),
        samesite="lax",
        path="/auth/google/callback",
    )


def _clear_google_state_cookie(response: RedirectResponse) -> None:
    response.delete_cookie(GOOGLE_OAUTH_STATE_COOKIE_NAME, path="/auth/google/callback")


def _cleanup_oauth_handoffs(now_ts: Optional[float] = None) -> None:
    now_value = float(now_ts if now_ts is not None else time.time())
    expired_codes = [
        code
        for code, (expires_at, _token) in _OAUTH_HANDOFF_STORE.items()
        if expires_at <= now_value
    ]
    for code in expired_codes:
        _OAUTH_HANDOFF_STORE.pop(code, None)


def _store_oauth_handoff_token(access_token: str) -> str:
    code = os.urandom(24).hex()
    expires_at = time.time() + OAUTH_HANDOFF_TTL_SECONDS
    with _OAUTH_HANDOFF_LOCK:
        _cleanup_oauth_handoffs()
        _OAUTH_HANDOFF_STORE[code] = (expires_at, access_token)
    return code


def _consume_oauth_handoff_token(code: str) -> Optional[str]:
    if not code:
        return None
    with _OAUTH_HANDOFF_LOCK:
        _cleanup_oauth_handoffs()
        row = _OAUTH_HANDOFF_STORE.pop(code, None)
    if not row:
        return None
    expires_at, access_token = row
    if expires_at <= time.time():
        return None
    return access_token


def _build_frontend_oauth_handoff_redirect(
    frontend_redirect: str, code: str
) -> RedirectResponse:
    return RedirectResponse(f"{frontend_redirect}#oauth_code={quote(code)}")


def _google_error_redirect(
    message: str,
    frontend_redirect: Optional[str] = None,
    *,
    clear_state_cookie: bool = False,
) -> RedirectResponse:
    target = _resolve_frontend_redirect(frontend_redirect)
    query = urlencode({"error": message})
    response = RedirectResponse(f"{target}/login?{query}")
    if clear_state_cookie:
        _clear_google_state_cookie(response)
    return response


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
        expire = _now_utc() + expires_delta
    else:
        expire = _now_utc() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "token_type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def _issue_session_tokens(user_email: str, user_id: int) -> tuple[str, str]:
    access_token = create_access_token(
        data={"sub": user_email, "uid": int(user_id)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token, _ = _create_refresh_token_for_user(int(user_id))
    return access_token, refresh_token


async def get_current_user(
    token: Optional[str] = Depends(_resolve_access_token),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """FastAPI dependency — resolves the current authenticated user.

    Always returns 401 for missing/invalid/expired tokens.
    Returns 403 for inactive (disabled) accounts.
    NEVER returns 500 for auth errors.
    """
    _401 = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # ── 1. Token presence check ─────────────────────────────────────────
    if not token:
        raise _401

    # ── 2. JWT decode — all token errors → 401 ─────────────────────────
    try:
        payload = _decode_access_token_or_401(token)
        email: str = str(payload.get("sub") or "").strip()
        if not email:
            raise _401
    except HTTPException:
        raise _401
    except Exception as exc:
        # Defensive: any unexpected decode error must never become a 500
        logging.warning("get_current_user: token decode error: %s", exc)
        raise _401

    # ── 3. User lookup — Firestore errors → 401 ─────────────────────────
    try:
        from utils.user_cache import get_cached_user, invalidate_user_cache  # noqa: F401

        normalized_email = _normalize_email(email)

        def _fetch(em: str):
            return _merge_duplicate_users_for_email(repo, em)

        user = get_cached_user(normalized_email, _fetch)
    except Exception as exc:
        logging.warning("get_current_user: user lookup error for %s: %s", email, exc)
        raise _401

    if user is None:
        raise _401

    # ── 4. Account status check — inactive accounts → 403 ──────────────
    if not getattr(user, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled. Contact support.",
        )

    return user




@router.post("/register")
async def register(
    user_data: UserCreate,
    request: Request,
    response: Response,
    repo: ResearchRepository = Depends(get_research_repository),
):
    normalized_email = _normalize_email(user_data.email)
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Email is required")
    # Check if user already exists
    existing_user = _merge_duplicate_users_for_email(repo, normalized_email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user
    password = _validate_password_or_400(user_data.password)
    hashed_password = get_password_hash(password)
    verification_token = (
        generate_verification_token() if EMAIL_VERIFICATION_REQUIRED else None
    )
    verification_expires = (
        get_verification_token_expiry() if EMAIL_VERIFICATION_REQUIRED else None
    )

    user = repo.create_user(
        email=normalized_email,
        hashed_password=hashed_password,
        is_verified=not EMAIL_VERIFICATION_REQUIRED,
        is_active=True,
        name=user_data.name,
        verification_token=verification_token,
        verification_token_expires=verification_expires,
    )

    if not EMAIL_VERIFICATION_REQUIRED:
        access_token, refresh_token = _issue_session_tokens(user.email, int(user.id))
        _set_auth_cookies(response, request, access_token, refresh_token)
        return {
            "message": "User registered successfully.",
            "access_token": access_token,
            "token_type": "bearer",
            "access_token_expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    # Send verification email when verification is required.
    if verification_token:
        try:
            await send_verification_email(user.email, verification_token, user.name)
        except Exception as e:
            logging.error(f"Failed to send verification email: {e}")
            # Do not fail registration if email delivery fails.

    return {
        "message": "User registered successfully. Please check your email to verify your account."
    }


@router.post("/verify-email")
async def verify_email(
    token: str,
    repo: ResearchRepository = Depends(get_research_repository),
):
    # Use indexed lookup if available, fall back to scan only as a last resort.
    user = None
    if hasattr(repo, "get_user_by_verification_token"):
        user = repo.get_user_by_verification_token(str(token or "").strip())
    else:
        user = next(
            (
                row
                for row in repo.list_users()
                if getattr(row, "verification_token", None) == token
            ),
            None,
        )
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification token")

    expires_at = user.verification_token_expires
    if not expires_at:
        raise HTTPException(status_code=400, detail="Verification token has expired")
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Verification token has expired")

    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    repo.save(user)

    return {"message": "Email verified successfully"}


@router.post("/resend-verification-email")
async def resend_verification_email(
    email: str,
    repo: ResearchRepository = Depends(get_research_repository),
):
    normalized_email = _normalize_email(email)
    user = repo.get_user_by_email(normalized_email)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    if user.is_verified:
        raise HTTPException(status_code=400, detail="Email is already verified")

    verification_token = generate_verification_token()
    verification_expires = get_verification_token_expiry()

    user.verification_token = verification_token
    user.verification_token_expires = verification_expires
    repo.save(user)

    try:
        await send_verification_email(user.email, verification_token, user.name)
    except Exception as e:
        logging.error(f"Failed to send verification email: {e}")
        # Don't fail registration if email fails, but log it

    return {"message": "Verification email resent successfully"}


@router.post("/token", response_model=Token)
def login_for_access_token(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    repo: ResearchRepository = Depends(get_research_repository),
):
    username = (form_data.username or "").strip().lower()
    user = _merge_duplicate_users_for_email(repo, username)
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
        password_ok = bool(user.hashed_password) and verify_password(
            form_data.password, user.hashed_password
        )
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
    access_token, refresh_token = _issue_session_tokens(user.email, int(user.id))
    _set_auth_cookies(response, request, access_token, refresh_token)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "access_token_expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


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
    auth_provider: Optional[str] = None
    managed_auth: bool = False


class ProfileUpdate(BaseModel):
    name: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class DeleteAccountRequest(BaseModel):
    confirm_email: str
    password: Optional[str] = None


@router.get("/me", response_model=UserOut)
async def get_me(current_user: Any = Depends(get_current_user)):
    auth_provider = (
        "google"
        if current_user.google_id
        else ("firebase" if not current_user.hashed_password else "password")
    )
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
        "auth_provider": auth_provider,
        "managed_auth": not bool(current_user.hashed_password),
    }


@router.get("/me/overview")
async def get_me_overview(
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: Any = Depends(get_current_user),
):
    workspace_rows = repo.list_workspaces_for_user(current_user.id)
    workspace_count = len(workspace_rows)
    paper_count = 0
    chat_count = 0
    doc_count = 0
    for workspace in workspace_rows:
        papers = repo.list_papers_for_workspace(workspace.id)
        paper_count += len(papers)
        chat_count += len(repo.list_chats_for_workspace(workspace.id))
        if repo.get_docspace_document(workspace.id, current_user.id):
            doc_count += 1

    search_count = repo.count_search_history_for_user(current_user.id)
    recent_search_rows = repo.list_search_history_for_user(current_user.id, limit=8)
    recent_workspace_rows = sorted(
        workspace_rows,
        key=lambda row: (
            row.created_at or datetime(1970, 1, 1, tzinfo=timezone.utc)
        ).timestamp(),
        reverse=True,
    )[:6]
    state = repo.get_session_state_for_user(current_user.id)

    now = datetime.now(timezone.utc)
    created_at = current_user.created_at
    if created_at and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    account_age_days = (
        max(0, int((now - created_at).total_seconds() // 86400)) if created_at else 0
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


@router.get("/google/login")
async def google_login(request: Request):
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    if not client_id or not os.getenv("GOOGLE_CLIENT_SECRET"):
        raise HTTPException(status_code=500, detail="Google OAuth is not configured")

    redirect_uri = _resolve_google_redirect_uri(request)
    frontend_redirect = _resolve_frontend_redirect(
        request.query_params.get("frontend_redirect")
    )
    state = _encode_google_oauth_state(frontend_redirect)
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
    response = RedirectResponse(authorization_url)
    _set_google_state_cookie(response, request, state)
    return response


@router.get("/google/status")
async def google_status():
    configured = bool(
        os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET")
    )
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    client_id_hint = f"{client_id[:14]}..." if client_id else None
    return {
        "configured": configured,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "frontend_url": FRONTEND_URL,
        "backend_url": BACKEND_URL,
        "client_id_hint": client_id_hint,
    }


@router.get("/firebase/status")
async def firebase_status():
    return {
        "configured": firebase_admin_is_configured(),
        "project_id": (os.getenv("FIREBASE_PROJECT_ID") or "").strip() or None,
        "app_check_enforced": (
            os.getenv("FIREBASE_APPCHECK_ENFORCED", "0").strip().lower()
            in {"1", "true", "yes"}
        ),
    }


@router.post("/firebase/session", response_model=Token)
async def firebase_session_exchange(
    payload: FirebaseSessionIn,
    request: Request,
    response: Response,
    repo: ResearchRepository = Depends(get_research_repository),
):
    if not firebase_admin_is_configured():
        raise HTTPException(
            status_code=503, detail="Firebase Authentication is not configured"
        )

    try:
        decoded = verify_firebase_id_token(payload.id_token)
    except Exception as exc:
        logging.exception("Firebase token verification failed")
        raise HTTPException(
            status_code=401, detail=f"Invalid Firebase session token: {exc}"
        ) from exc

    email = _normalize_email(decoded.get("email"))
    if not email:
        raise HTTPException(
            status_code=400, detail="Firebase token does not contain an email address"
        )

    if decoded.get("email_verified") is False:
        raise HTTPException(status_code=403, detail="Firebase email is not verified")

    name = decoded.get("name")
    picture = decoded.get("picture")
    uid = str(decoded.get("uid") or decoded.get("sub") or "").strip() or None
    provider = firebase_sign_in_provider(decoded)

    user = _merge_duplicate_users_for_email(repo, email)
    if not user:
        user = repo.create_user(
            email=email,
            google_id=uid if provider == "google.com" else None,
            google_email=email if provider == "google.com" else None,
            name=name,
            profile_pic=picture,
            is_verified=True,
            is_active=True,
        )
    else:
        user.email = email
        user.is_verified = True
        user.is_active = True
        user.name = name or user.name
        user.profile_pic = picture or user.profile_pic
        if provider == "google.com":
            user.google_id = user.google_id or uid
            user.google_email = email
        repo.save(user)

    access_token, refresh_token = _issue_session_tokens(user.email, int(user.id))
    _set_auth_cookies(response, request, access_token, refresh_token)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/oauth/exchange", response_model=Token)
async def oauth_exchange(
    payload: OAuthExchangeIn, request: Request, response: Response
):
    code = str(payload.code or "").strip()
    access_token = _consume_oauth_handoff_token(code)
    if not access_token:
        raise HTTPException(
            status_code=400, detail="OAuth sign-in session is invalid or has expired."
        )
    payload_decoded = _decode_access_token_or_401(access_token)
    email = str(payload_decoded.get("sub") or "").strip()
    user_id = int(payload_decoded.get("uid") or 0)
    if not email or user_id <= 0:
        raise HTTPException(
            status_code=400, detail="OAuth sign-in session payload is invalid."
        )
    refresh_token, _expires_at = _create_refresh_token_for_user(user_id)
    _set_auth_cookies(response, request, access_token, refresh_token)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh", response_model=Token)
async def refresh_session(
    request: Request,
    response: Response,
    repo: ResearchRepository = Depends(get_research_repository),
):
    raw_refresh_token = str(
        request.cookies.get(REFRESH_TOKEN_COOKIE_NAME) or ""
    ).strip()
    if not raw_refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token.")
    rotated = _rotate_refresh_token(raw_refresh_token)
    if not rotated:
        _clear_auth_cookies(response, request)
        raise HTTPException(
            status_code=401, detail="Refresh token is invalid or expired."
        )
    user_id, new_refresh_token, _expires_at = rotated
    user = repo.get_user_by_id(user_id)
    if not user:
        _clear_auth_cookies(response, request)
        raise HTTPException(
            status_code=401, detail="Refresh token user no longer exists."
        )
    access_token = create_access_token(
        data={"sub": str(user.email), "uid": int(user.id)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    _set_auth_cookies(response, request, access_token, new_refresh_token)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
async def logout(request: Request, response: Response):
    raw_refresh_token = str(
        request.cookies.get(REFRESH_TOKEN_COOKIE_NAME) or ""
    ).strip()
    if raw_refresh_token:
        _mark_refresh_token_revoked(raw_refresh_token)
    _clear_auth_cookies(response, request)
    return {"message": "Logged out"}


@router.get("/google/callback")
async def google_callback(
    request: Request,
    repo: ResearchRepository = Depends(get_research_repository),
):
    raw_state = str(request.query_params.get("state") or "").strip()
    cookie_state = str(
        request.cookies.get(GOOGLE_OAUTH_STATE_COOKIE_NAME) or ""
    ).strip()
    frontend_redirect = FRONTEND_URL
    try:
        if not raw_state or not cookie_state or raw_state != cookie_state:
            raise InvalidTokenError("Google OAuth state mismatch.")
        state_payload = _decode_google_oauth_state(raw_state)
        frontend_redirect = _resolve_frontend_redirect(
            state_payload.get("frontend_redirect")
        )
    except Exception:
        return _google_error_redirect(
            "Google sign-in state was invalid or expired. Please retry.",
            frontend_redirect,
            clear_state_cookie=True,
        )

    if request.query_params.get("error"):
        error_description = request.query_params.get("error_description")
        message = "Google sign-in was cancelled or denied."
        if error_description:
            message = f"Google sign-in failed: {error_description}"
        return _google_error_redirect(
            message, frontend_redirect, clear_state_cookie=True
        )

    code = request.query_params.get("code")
    if not code:
        return _google_error_redirect(
            "Missing authorization code from Google.",
            frontend_redirect,
            clear_state_cookie=True,
        )

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
            access_token = (
                token_payload.get("access_token")
                if isinstance(token_payload, dict)
                else None
            )
            if not access_token:
                raise RuntimeError("Google OAuth token response missing access_token")

            userinfo_resp = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_resp.raise_for_status()
            user_info = userinfo_resp.json()
        google_id = user_info.get("sub")
        email = _normalize_email(user_info.get("email"))
        if not google_id or not email:
            logging.warning("Google userinfo missing required fields: %s", user_info)
            return _google_error_redirect(
                "Google account info was incomplete. Please try again.",
                frontend_redirect,
                clear_state_cookie=True,
            )
        if user_info.get("email_verified") is False:
            return _google_error_redirect(
                "Google email is not verified. Use a verified account.",
                frontend_redirect,
                clear_state_cookie=True,
            )
        name = user_info.get("name")
        picture = user_info.get("picture")
    except Exception as exc:
        logging.exception("Google OAuth callback failed")
        return _google_error_redirect(
            _friendly_google_oauth_error(exc),
            frontend_redirect,
            clear_state_cookie=True,
        )

    # Reconcile fragmented accounts by email first (handles legacy rows with
    # mixed casing/spacing or rows that only had google_email set).
    merged_email_user = _merge_duplicate_users_for_email(repo, email)
    user_by_google = repo.get_user_by_google_id(google_id)

    if (
        user_by_google
        and merged_email_user
        and user_by_google.id != merged_email_user.id
    ):
        # Keep the richer merged-email account as primary and move Google identity to it.
        merged_email_user.google_id = google_id
        merged_email_user.google_email = email
        merged_email_user.email = email
        merged_email_user.name = merged_email_user.name or name
        merged_email_user.profile_pic = merged_email_user.profile_pic or picture
        merged_email_user.is_verified = True

        user = merged_email_user
        repo.merge_user_accounts(merged_email_user.id, user_by_google.id)
    elif user_by_google:
        user = user_by_google
    elif merged_email_user:
        user = merged_email_user
        user.google_id = google_id
        user.google_email = email
        user.email = email
    else:
        user = User(
            id=None,
            email=email,
            google_id=google_id,
            google_email=email,
            name=name,
            profile_pic=picture,
            is_verified=True,
        )

    user.email = email
    user.google_email = email
    user.google_id = google_id
    user.name = name or user.name
    user.profile_pic = picture or user.profile_pic
    user.is_verified = True
    try:
        user = repo.save(user)
    except Exception:
        logging.exception("Failed to persist Google user during callback")
        return _google_error_redirect(
            "Account linking failed. Try signing in again.",
            frontend_redirect,
            clear_state_cookie=True,
        )

    access_token = create_access_token(
        data={"sub": user.email, "uid": int(user.id)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    handoff_code = _store_oauth_handoff_token(access_token)
    response = _build_frontend_oauth_handoff_redirect(frontend_redirect, handoff_code)
    _clear_google_state_cookie(response)
    return response


@router.patch("/me")
async def update_profile(
    profile_data: ProfileUpdate,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: Any = Depends(get_current_user),
):
    if profile_data.name is not None:
        current_user.name = profile_data.name
    repo.save(current_user)
    return {"message": "Profile updated successfully"}


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: Any = Depends(get_current_user),
):
    # Only allow password change for non-Google users
    if not current_user.hashed_password:
        raise HTTPException(
            status_code=400,
            detail="Password changes are managed by your identity provider",
        )

    if not verify_password(
        password_data.current_password, current_user.hashed_password
    ):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    new_password = _validate_password_or_400(password_data.new_password)
    current_user.hashed_password = get_password_hash(new_password)
    repo.save(current_user)
    return {"message": "Password changed successfully"}


@router.delete("/me")
async def delete_account(
    delete_data: DeleteAccountRequest,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: Any = Depends(get_current_user),
):
    if delete_data.confirm_email.strip().lower() != current_user.email.lower():
        raise HTTPException(
            status_code=400, detail="Confirmation email does not match your account"
        )

    if current_user.hashed_password:
        if not delete_data.password:
            raise HTTPException(
                status_code=400, detail="Password is required to delete account"
            )
        if not verify_password(delete_data.password, current_user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
    repo.delete_user_account(current_user.id)
    return {"message": "Account deleted successfully"}


# ---------------------------------------------------------------------------
# Password reset endpoints (forgot-password / reset-password)
# ---------------------------------------------------------------------------


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordIn,
    repo: ResearchRepository = Depends(get_research_repository),
):
    """Send a password-reset email.  Always returns 200 to prevent user enumeration."""
    normalized = _normalize_email(payload.email)
    user = repo.get_user_by_email(normalized)

    # Don't reveal whether the email exists; fire-and-forget email send.
    if user and getattr(user, "hashed_password", None):
        reset_token = generate_verification_token()
        reset_expires = _now_utc() + timedelta(
            minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        )
        # Reuse verification_token fields for password reset (same lifecycle).
        user.verification_token = reset_token
        user.verification_token_expires = reset_expires
        try:
            repo.save(user)
            await send_password_reset_email(
                normalized, reset_token, getattr(user, "name", None)
            )
        except Exception:
            logging.exception("Failed to send password reset email for %s", normalized)

    return {
        "message": "If an account with that email exists, a password reset link has been sent."
    }


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordIn,
    repo: ResearchRepository = Depends(get_research_repository),
):
    """Consume a password-reset token and update the user's password."""
    token = str(payload.token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Reset token is required.")

    # Find user by reset token — use indexed lookup via get_user_by_verification_token
    # if the repository supports it, otherwise fall back to list scan (small result set
    # because tokens expire in 1 hour and are one-time-use).
    user = None
    if hasattr(repo, "get_user_by_verification_token"):
        user = repo.get_user_by_verification_token(token)
    else:
        # Fallback: scan all users (safe only for small user bases or Firebase where
        # collection is queried with a where clause by the repository).
        user = next(
            (
                u
                for u in repo.list_users()
                if getattr(u, "verification_token", None) == token
            ),
            None,
        )

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    expires_at = getattr(user, "verification_token_expires", None)
    if not expires_at:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < _now_utc():
        raise HTTPException(
            status_code=400, detail="Reset token has expired. Please request a new one."
        )

    if not getattr(user, "hashed_password", None):
        raise HTTPException(
            status_code=400,
            detail="This account uses Google sign-in and does not have a password to reset.",
        )

    new_password = _validate_password_or_400(payload.new_password)
    user.hashed_password = get_password_hash(new_password)
    user.verification_token = None
    user.verification_token_expires = None
    repo.save(user)
    return {
        "message": "Password has been reset successfully. You can now sign in with your new password."
    }
