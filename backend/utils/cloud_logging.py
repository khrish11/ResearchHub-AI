from __future__ import annotations

import logging
import os

try:
    from google.cloud import logging as cloud_logging
except Exception:  # pragma: no cover - optional dependency
    cloud_logging = None


def setup_google_cloud_logging() -> None:
    enabled = (os.getenv("GOOGLE_CLOUD_LOGGING_ENABLED") or "0").strip().lower() in {"1", "true", "yes"}
    project_id = (os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("FIREBASE_PROJECT_ID") or "").strip()
    if not enabled or not project_id or cloud_logging is None:
        return
    try:
        client = cloud_logging.Client(project=project_id)
        client.setup_logging(log_level=logging.INFO)
    except Exception:
        logging.getLogger(__name__).exception("Failed to initialize Google Cloud Logging")
