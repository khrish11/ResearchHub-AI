from __future__ import annotations

import os


IS_PRODUCTION = (os.getenv("APP_ENV") or "").strip().lower() == "production"
ALLOWED_FRONTEND_ORIGIN = (
    os.getenv("FRONTEND_URL") or "https://research-hub-ai-lime.vercel.app"
).rstrip("/")
MAX_LATENCY_SECONDS = 4.0 if IS_PRODUCTION else 2.0
