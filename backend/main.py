# ---------------------------------------------------------------------------
# Compatibility patch: passlib 1.7.4 looks for bcrypt.__about__.__version__
# which was removed in bcrypt 4.x.  Inject it so passlib stops complaining.
# ---------------------------------------------------------------------------
import bcrypt as _bcrypt
if not hasattr(_bcrypt, '__about__'):
    class _About:
        __version__ = getattr(_bcrypt, '__version__', '4.0.1')
    _bcrypt.__about__ = _About()
# ---------------------------------------------------------------------------

# Load environment variables early so routers that read os.getenv() at import
# time will see values from backend/.env (prevents missing-key issues).
# Important: keep process env precedence (override=False). This prevents
# accidentally clobbering explicit DATABASE_URL values (e.g. during tests),
# which can otherwise lead to data appearing to "disappear" across runs.
from dotenv import load_dotenv
from pathlib import Path
BACKEND_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=BACKEND_ENV_PATH, override=False)
load_dotenv(override=False)
from utils.secret_manager import bootstrap_secret_manager_env
bootstrap_secret_manager_env()

# Enforce secure configuration in production
import os
import logging
import json
import ipaddress
import time
from collections import deque
from threading import Lock
from typing import Any, Deque, Dict, Optional, Tuple
from uuid import uuid4

try:
    import redis
except Exception:  # pragma: no cover - optional runtime dependency
    redis = None  # type: ignore[assignment]
APP_ENV = os.getenv("APP_ENV", "production")
SECRET_KEY = os.getenv("SECRET_KEY")
if APP_ENV != "development" and (not SECRET_KEY or SECRET_KEY == "secret"):
    raise RuntimeError("SECRET_KEY must be set and not 'secret' in production (configure backend/.env or process env).")

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.middleware.gzip import GZipMiddleware


from routers import auth, papers, chat, workspaces, ai, upload, research_agent, developer, compliance
from sqlalchemy import text
from database import engine, Base
from repositories import FirebaseResearchRepository
from utils.cloud_logging import setup_google_cloud_logging
from utils.firebase_admin_client import verify_firebase_app_check_token

logger = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger.setLevel(logging.INFO)
setup_google_cloud_logging()

RATE_LIMIT_ENABLED = (
    os.getenv("RATE_LIMIT_ENABLED", "1" if APP_ENV != "development" else "0")
    .strip()
    .lower()
    in {"1", "true", "yes"}
)
RATE_LIMIT_WINDOW_SECONDS = max(10, int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60") or 60))
RATE_LIMIT_AUTH_PER_WINDOW = max(10, int(os.getenv("RATE_LIMIT_AUTH_PER_WINDOW", "90") or 90))
RATE_LIMIT_API_PER_WINDOW = max(40, int(os.getenv("RATE_LIMIT_API_PER_WINDOW", "300") or 300))
SECURITY_HEADERS_ENABLED = (
    os.getenv("SECURITY_HEADERS_ENABLED", "1").strip().lower() in {"1", "true", "yes"}
)
METRICS_AUTH_TOKEN = str(os.getenv("METRICS_AUTH_TOKEN", "")).strip()
STORAGE_BACKEND = (os.getenv("STORAGE_BACKEND") or "sqlalchemy").strip().lower()
FIREBASE_APPCHECK_ENFORCED = (
    os.getenv("FIREBASE_APPCHECK_ENFORCED", "0").strip().lower() in {"1", "true", "yes"}
)
FIREBASE_APPCHECK_ALLOW_LOCALHOST = (
    os.getenv("FIREBASE_APPCHECK_ALLOW_LOCALHOST", "1").strip().lower() in {"1", "true", "yes"}
)
GOOGLE_CLOUD_PROJECT = (os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("FIREBASE_PROJECT_ID") or "").strip()
TRUST_PROXY_HEADERS = (
    os.getenv("TRUST_PROXY_HEADERS", "0").strip().lower() in {"1", "true", "yes"}
)
TRUSTED_PROXY_IPS = {
    value.strip()
    for value in (os.getenv("TRUSTED_PROXY_IPS") or "127.0.0.1,::1").split(",")
    if value.strip()
}
RATE_LIMIT_STORE = (os.getenv("RATE_LIMIT_STORE") or "memory").strip().lower()
REDIS_URL = (os.getenv("REDIS_URL") or "").strip()

_RATE_LIMIT_BUCKETS: Dict[str, Deque[float]] = {}
_RATE_LIMIT_LOCK = Lock()
_METRICS_LOCK = Lock()
_HTTP_METRICS: Dict[str, Any] = {
    "started_at": time.time(),
    "requests_total": 0,
    "rate_limited_total": 0,
    "status_counts": {},
    "path_counts": {},
    "latency_buckets_ms": {
        "le_50": 0,
        "le_100": 0,
        "le_250": 0,
        "le_500": 0,
        "le_1000": 0,
        "gt_1000": 0,
    },
}
_RECENT_REQUESTS: Deque[Tuple[float, int, int]] = deque(maxlen=15000)
_REDIS_RATE_LIMITER = None

if RATE_LIMIT_STORE == "redis":
    if not redis or not REDIS_URL:
        logger.warning("RATE_LIMIT_STORE=redis is configured but redis client/REDIS_URL is unavailable; falling back to memory.")
    else:
        try:
            _REDIS_RATE_LIMITER = redis.Redis.from_url(REDIS_URL, decode_responses=True)
            _REDIS_RATE_LIMITER.ping()
        except Exception as exc:
            logger.warning("Redis rate limiter init failed (%s); falling back to memory.", exc)
            _REDIS_RATE_LIMITER = None

if STORAGE_BACKEND == "sqlalchemy":
    Base.metadata.create_all(bind=engine)
elif STORAGE_BACKEND != "firebase":
    raise RuntimeError(f"Unsupported STORAGE_BACKEND '{STORAGE_BACKEND}'.")

app = FastAPI(title="Soyog AI API", version="1.0.0")

frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
allowed_origins = {
    frontend_url,
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(allowed_origins),
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=512)


def _is_https_request(request: Request) -> bool:
    forwarded = str(request.headers.get("x-forwarded-proto", "")).split(",")[0].strip().lower()
    return request.url.scheme == "https" or forwarded == "https"


def _direct_client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _normalize_ip(value: Optional[str]) -> Optional[str]:
    candidate = str(value or "").strip()
    if not candidate:
        return None
    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1:candidate.index("]")]
    elif candidate.count(":") == 1 and "." in candidate:
        candidate = candidate.rsplit(":", 1)[0]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        lowered = candidate.lower()
        if lowered == "localhost":
            return "127.0.0.1"
        return None


def _extract_forwarded_ip(request: Request) -> Optional[str]:
    forwarded_for = str(request.headers.get("x-forwarded-for", "")).split(",")[0].strip()
    return _normalize_ip(forwarded_for)


def _is_trusted_proxy_request(request: Request) -> bool:
    if not TRUST_PROXY_HEADERS:
        return False
    direct_ip = _normalize_ip(_direct_client_ip(request))
    return bool(direct_ip and direct_ip in TRUSTED_PROXY_IPS)


def _is_local_direct_client(request: Request) -> bool:
    direct_raw = str(_direct_client_ip(request) or "").strip().lower()
    direct_ip = _normalize_ip(direct_raw)
    return direct_raw == "localhost" or direct_ip in {"127.0.0.1", "::1"}


def _resolve_client_ip(request: Request) -> str:
    direct_ip = _normalize_ip(_direct_client_ip(request))
    if _is_trusted_proxy_request(request):
        forwarded_ip = _extract_forwarded_ip(request)
        if forwarded_ip:
            return forwarded_ip
    if direct_ip:
        return direct_ip
    direct_raw = str(_direct_client_ip(request) or "").strip()
    return direct_raw or "unknown"


def _resolve_cloud_trace(request: Request) -> Optional[str]:
    if not GOOGLE_CLOUD_PROJECT:
        return None
    trace_header = str(request.headers.get("x-cloud-trace-context", "")).strip()
    if not trace_header:
        return None
    trace_id = trace_header.split("/", 1)[0].strip()
    if not trace_id:
        return None
    return f"projects/{GOOGLE_CLOUD_PROJECT}/traces/{trace_id}"


def _rate_limit_scope(path: str) -> Optional[Tuple[str, int]]:
    if path in {"/health/live", "/health/ready", "/ops/metrics", "/ops/slo", "/"}:
        return None
    if path.startswith(("/docs", "/redoc", "/openapi.json")):
        return None
    if path.startswith("/auth/"):
        return "auth", RATE_LIMIT_AUTH_PER_WINDOW
    return "api", RATE_LIMIT_API_PER_WINDOW


def _check_rate_limit(request: Request) -> Tuple[bool, int]:
    if not RATE_LIMIT_ENABLED:
        return True, 0
    scope = _rate_limit_scope(request.url.path)
    if not scope:
        return True, 0
    scope_name, limit = scope
    if limit <= 0:
        return True, 0

    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    key = f"{scope_name}:{_resolve_client_ip(request)}"

    if _REDIS_RATE_LIMITER is not None:
        window_bucket = int(now // RATE_LIMIT_WINDOW_SECONDS)
        redis_key = f"researchhub:ratelimit:{key}:{window_bucket}"
        try:
            count = int(_REDIS_RATE_LIMITER.incr(redis_key))
            if count == 1:
                _REDIS_RATE_LIMITER.expire(redis_key, RATE_LIMIT_WINDOW_SECONDS + 2)
            if count > limit:
                retry_after = int(max(1, RATE_LIMIT_WINDOW_SECONDS - (now % RATE_LIMIT_WINDOW_SECONDS)))
                return False, retry_after
            return True, 0
        except Exception as exc:
            logger.warning("Redis rate limiting failed (%s); using memory fallback.", exc)

    with _RATE_LIMIT_LOCK:
        bucket = _RATE_LIMIT_BUCKETS.get(key)
        if bucket is None:
            bucket = deque()
            _RATE_LIMIT_BUCKETS[key] = bucket

        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            retry_after = int(max(1, round((bucket[0] + RATE_LIMIT_WINDOW_SECONDS) - now)))
            return False, retry_after

        bucket.append(now)
        # Opportunistic cleanup for stale keys.
        if len(_RATE_LIMIT_BUCKETS) > 4000:
            stale_keys = [k for k, v in _RATE_LIMIT_BUCKETS.items() if (not v) or (v and v[-1] <= cutoff)]
            for stale_key in stale_keys[:500]:
                _RATE_LIMIT_BUCKETS.pop(stale_key, None)
    return True, 0


def _metric_path(path: str) -> str:
    segments = []
    for part in str(path or "/").split("/"):
        if not part:
            continue
        if part.isdigit():
            segments.append(":id")
            continue
        if len(part) >= 24 and all(ch in "0123456789abcdefABCDEF" for ch in part):
            segments.append(":id")
            continue
        segments.append(part[:40])
    return "/" + "/".join(segments[:6]) if segments else "/"


def _update_http_metrics(path: str, status_code: int, duration_ms: int, rate_limited: bool = False) -> None:
    now = time.time()
    path_key = _metric_path(path)
    with _METRICS_LOCK:
        _HTTP_METRICS["requests_total"] = int(_HTTP_METRICS.get("requests_total", 0)) + 1
        if rate_limited:
            _HTTP_METRICS["rate_limited_total"] = int(_HTTP_METRICS.get("rate_limited_total", 0)) + 1

        status_counts = _HTTP_METRICS.setdefault("status_counts", {})
        status_key = str(status_code)
        status_counts[status_key] = int(status_counts.get(status_key, 0)) + 1

        path_counts = _HTTP_METRICS.setdefault("path_counts", {})
        path_counts[path_key] = int(path_counts.get(path_key, 0)) + 1
        if len(path_counts) > 2000:
            stale = sorted(path_counts.items(), key=lambda item: item[1])[:400]
            for stale_key, _ in stale:
                path_counts.pop(stale_key, None)

        buckets = _HTTP_METRICS.setdefault("latency_buckets_ms", {})
        if duration_ms <= 50:
            buckets["le_50"] = int(buckets.get("le_50", 0)) + 1
        elif duration_ms <= 100:
            buckets["le_100"] = int(buckets.get("le_100", 0)) + 1
        elif duration_ms <= 250:
            buckets["le_250"] = int(buckets.get("le_250", 0)) + 1
        elif duration_ms <= 500:
            buckets["le_500"] = int(buckets.get("le_500", 0)) + 1
        elif duration_ms <= 1000:
            buckets["le_1000"] = int(buckets.get("le_1000", 0)) + 1
        else:
            buckets["gt_1000"] = int(buckets.get("gt_1000", 0)) + 1

        _RECENT_REQUESTS.append((now, int(status_code), int(duration_ms)))


def _window_slo(window_seconds: int) -> Dict[str, Any]:
    cutoff = time.time() - max(1, int(window_seconds))
    status_ok = 0
    status_total = 0
    latency_samples = []
    with _METRICS_LOCK:
        for ts, code, latency in _RECENT_REQUESTS:
            if ts < cutoff:
                continue
            status_total += 1
            if 200 <= int(code) < 500:
                status_ok += 1
            latency_samples.append(int(latency))
    if not status_total:
        return {"requests": 0, "availability_pct": 100.0, "p95_ms": 0, "p99_ms": 0}
    latency_samples.sort()
    idx95 = max(0, min(len(latency_samples) - 1, int(len(latency_samples) * 0.95) - 1))
    idx99 = max(0, min(len(latency_samples) - 1, int(len(latency_samples) * 0.99) - 1))
    return {
        "requests": status_total,
        "availability_pct": round((status_ok / status_total) * 100.0, 3),
        "p95_ms": int(latency_samples[idx95]),
        "p99_ms": int(latency_samples[idx99]),
    }


def _apply_response_headers(response, request: Request, request_id: str, duration_ms: int) -> None:
    response.headers["X-Process-Time-Ms"] = str(duration_ms)
    response.headers["X-Request-ID"] = request_id
    if not SECURITY_HEADERS_ENABLED:
        return

    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")

    if _is_https_request(request):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

    if request.url.path.startswith("/auth/"):
        response.headers.setdefault("Cache-Control", "no-store")

    if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        )


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    started = time.perf_counter()
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    status_code = 500
    cloud_trace = _resolve_cloud_trace(request)

    if FIREBASE_APPCHECK_ENFORCED:
        allow_local = FIREBASE_APPCHECK_ALLOW_LOCALHOST and _is_local_direct_client(request)
        if not allow_local and not request.url.path.startswith(("/health/", "/docs", "/redoc", "/openapi.json", "/auth/google/", "/auth/firebase/status")):
            app_check_token = (
                request.headers.get("X-Firebase-AppCheck")
                or request.headers.get("X-Firebase-Appcheck")
                or request.headers.get("X-Firebase-AppCheck-Token")
            )
            if not app_check_token:
                duration_ms = int((time.perf_counter() - started) * 1000)
                response = JSONResponse(status_code=401, content={"detail": "Missing Firebase App Check token."})
                _apply_response_headers(response, request, request_id, duration_ms)
                _update_http_metrics(request.url.path, 401, duration_ms)
                return response
            try:
                verify_firebase_app_check_token(str(app_check_token))
            except Exception as exc:
                logger.warning("Firebase App Check verification failed: %s", exc)
                duration_ms = int((time.perf_counter() - started) * 1000)
                response = JSONResponse(status_code=401, content={"detail": "Invalid Firebase App Check token."})
                _apply_response_headers(response, request, request_id, duration_ms)
                _update_http_metrics(request.url.path, 401, duration_ms)
                return response

    allowed, retry_after = _check_rate_limit(request)
    if not allowed:
        duration_ms = int((time.perf_counter() - started) * 1000)
        response = JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please retry shortly."},
        )
        response.headers["Retry-After"] = str(retry_after)
        _apply_response_headers(response, request, request_id, duration_ms)
        _update_http_metrics(request.url.path, 429, duration_ms, rate_limited=True)
        logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 429,
                    "duration_ms": duration_ms,
                    "rate_limited": True,
                    "retry_after_s": retry_after,
                    "logging.googleapis.com/trace": cloud_trace,
                }
            )
        )
        return response

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        duration_ms = int((time.perf_counter() - started) * 1000)
        _update_http_metrics(request.url.path, 500, duration_ms)
        logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                    "logging.googleapis.com/trace": cloud_trace,
                }
            )
        )
        raise

    duration_ms = int((time.perf_counter() - started) * 1000)
    _apply_response_headers(response, request, request_id, duration_ms)
    _update_http_metrics(request.url.path, status_code, duration_ms)
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "logging.googleapis.com/trace": cloud_trace,
            }
        )
    )
    return response

app.include_router(auth.router)
app.include_router(workspaces.router)
app.include_router(papers.router)
app.include_router(chat.router)
app.include_router(ai.router)
app.include_router(upload.router)
app.include_router(research_agent.router)
app.include_router(developer.router)
app.include_router(compliance.router)

logger.info(
    json.dumps(
        {
            "event": "startup_config",
            "app_env": APP_ENV,
            "backend_env_path": str(BACKEND_ENV_PATH),
            "storage_backend": STORAGE_BACKEND,
            "database_url": str(engine.url),
        }
    )
)


@app.get("/health/live")
async def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    if STORAGE_BACKEND == "firebase":
        try:
            repo = FirebaseResearchRepository()
            next(repo.users.limit(1).stream(), None)
        except Exception as exc:
            logger.warning("Firebase readiness check failed: %s", exc)
            return JSONResponse(
                status_code=503,
                content={"status": "degraded", "database": "unavailable", "storage_backend": "firebase"},
            )
        return {"status": "ok", "database": "up", "storage_backend": "firebase"}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Readiness check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "unavailable", "storage_backend": "sqlalchemy"},
        )
    return {"status": "ok", "database": "up", "storage_backend": "sqlalchemy"}


def _require_metrics_token(request: Request) -> None:
    if not METRICS_AUTH_TOKEN:
        return
    supplied = str(request.headers.get("X-Metrics-Token", "")).strip()
    if supplied != METRICS_AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized metrics access")


@app.get("/ops/slo")
async def ops_slo(request: Request):
    _require_metrics_token(request)
    last_5m = _window_slo(5 * 60)
    last_1h = _window_slo(60 * 60)
    return {
        "targets": {
            "availability_pct": 99.9,
            "p95_ms": 500,
        },
        "windows": {
            "5m": last_5m,
            "1h": last_1h,
        },
    }


@app.get("/ops/metrics")
async def ops_metrics(request: Request):
    _require_metrics_token(request)
    now = time.time()
    with _METRICS_LOCK:
        metrics = {
            "started_at": float(_HTTP_METRICS.get("started_at", now)),
            "requests_total": int(_HTTP_METRICS.get("requests_total", 0)),
            "rate_limited_total": int(_HTTP_METRICS.get("rate_limited_total", 0)),
            "status_counts": dict(_HTTP_METRICS.get("status_counts", {})),
            "path_counts": dict(_HTTP_METRICS.get("path_counts", {})),
            "latency_buckets_ms": dict(_HTTP_METRICS.get("latency_buckets_ms", {})),
        }

    lines = [
        "# HELP researchhub_http_requests_total Total HTTP requests handled by API",
        "# TYPE researchhub_http_requests_total counter",
        f"researchhub_http_requests_total {metrics['requests_total']}",
        "# HELP researchhub_http_rate_limited_total Total HTTP requests blocked by rate limiting",
        "# TYPE researchhub_http_rate_limited_total counter",
        f"researchhub_http_rate_limited_total {metrics['rate_limited_total']}",
        "# HELP researchhub_uptime_seconds Process uptime in seconds",
        "# TYPE researchhub_uptime_seconds gauge",
        f"researchhub_uptime_seconds {int(max(0, now - metrics['started_at']))}",
    ]

    for status_code, count in sorted(metrics["status_counts"].items()):
        lines.append(
            f'researchhub_http_status_total{{status="{status_code}"}} {int(count)}'
        )
    for path_key, count in sorted(metrics["path_counts"].items()):
        escaped_path = path_key.replace("\\", "/").replace('"', '\\"')
        lines.append(
            f'researchhub_http_path_total{{path="{escaped_path}"}} {int(count)}'
        )
    for bucket_key, count in sorted(metrics["latency_buckets_ms"].items()):
        lines.append(
            f'researchhub_http_latency_bucket_total{{bucket="{bucket_key}"}} {int(count)}'
        )
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@app.get("/")
async def root():
    return {"message": "Soyog AI API is running"}
