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
# Use override=True in dev to ensure changes to backend/.env take effect when the
# server starts (helps avoid token/proc-env mismatches during local development).
from dotenv import load_dotenv
from pathlib import Path
BACKEND_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=BACKEND_ENV_PATH, override=True)
load_dotenv(override=False)

# Enforce secure configuration in production
import os
import logging
import json
import time
APP_ENV = os.getenv("APP_ENV", "production")
SECRET_KEY = os.getenv("SECRET_KEY")
if APP_ENV != "development" and (not SECRET_KEY or SECRET_KEY == "secret"):
    raise RuntimeError("SECRET_KEY must be set and not 'secret' in production (configure backend/.env or process env).")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware


from routers import auth, papers, chat, workspaces, ai, upload
from sqlalchemy import text
from database import engine, Base

logger = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger.setLevel(logging.INFO)

# Create tables
Base.metadata.create_all(bind=engine)

# Lightweight SQLite schema sync for local/dev DBs that may predate new columns.
# For production-grade deployments, use real migrations (e.g., Alembic).
if engine.dialect.name == "sqlite":
    with engine.begin() as conn:
        try:
            users_res = conn.execute(text("PRAGMA table_info('users')")).fetchall()
            users_cols = {r[1] for r in users_res}
            if 'google_id' not in users_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN google_id VARCHAR"))
            if 'google_email' not in users_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN google_email VARCHAR"))
            if 'name' not in users_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN name VARCHAR"))
            if 'profile_pic' not in users_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN profile_pic VARCHAR"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_id ON users (google_id)"))
        except Exception as exc:
            if APP_ENV == "development":
                logger.warning("Non-fatal users schema sync issue: %s", exc)
            else:
                raise RuntimeError(f"Users schema sync failed: {exc}") from exc

        try:
            papers_res = conn.execute(text("PRAGMA table_info('papers')")).fetchall()
            papers_cols = {r[1] for r in papers_res}
            if 'doi' not in papers_cols:
                conn.execute(text("ALTER TABLE papers ADD COLUMN doi VARCHAR"))
            if 'bibcode' not in papers_cols:
                conn.execute(text("ALTER TABLE papers ADD COLUMN bibcode VARCHAR"))
        except Exception as exc:
            if APP_ENV == "development":
                logger.warning("Non-fatal papers schema sync issue: %s", exc)
            else:
                raise RuntimeError(f"Papers schema sync failed: {exc}") from exc

app = FastAPI(title="ResearchHub AI API", version="1.0.0")

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


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                }
            )
        )
        raise
    duration_ms = int((time.perf_counter() - started) * 1000)
    response.headers["X-Process-Time-Ms"] = str(duration_ms)
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
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


@app.get("/")
async def root():
    return {"message": "ResearchHub AI API is running"}
