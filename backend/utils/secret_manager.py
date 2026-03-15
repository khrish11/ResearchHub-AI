from __future__ import annotations

import os
from typing import Iterable, Optional

try:
    from google.cloud import secretmanager
except Exception:  # pragma: no cover - optional dependency
    secretmanager = None


def _parse_secret_ref(value: str) -> tuple[str, str, str] | None:
    raw = str(value or "").strip()
    if not raw.startswith("sm://"):
        return None
    parts = [part for part in raw[5:].split("/") if part]
    if not parts:
        return None

    project_id = (os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("FIREBASE_PROJECT_ID") or "").strip()
    secret_name = ""
    version = "latest"

    if len(parts) == 1:
        secret_name = parts[0]
    elif len(parts) >= 2:
        if parts[1] == "versions":
            secret_name = parts[0]
            if len(parts) >= 3:
                version = parts[2]
        else:
            project_id = parts[0]
            secret_name = parts[1]
            if len(parts) >= 4 and parts[2] == "versions":
                version = parts[3]

    if not project_id or not secret_name:
        return None
    return project_id, secret_name, version


def resolve_secret_ref(value: str) -> Optional[str]:
    parsed = _parse_secret_ref(value)
    if not parsed or secretmanager is None:
        return None
    project_id, secret_name, version = parsed
    client = secretmanager.SecretManagerServiceClient()
    secret_path = client.secret_version_path(project_id, secret_name, version)
    response = client.access_secret_version(request={"name": secret_path})
    return response.payload.data.decode("utf-8")


def bootstrap_secret_manager_env(keys: Iterable[str] | None = None) -> None:
    if (os.getenv("GOOGLE_CLOUD_SECRET_MANAGER_ENABLED") or "0").strip().lower() not in {"1", "true", "yes"}:
        return
    target_keys = list(keys) if keys is not None else list(os.environ.keys())
    for key in target_keys:
        current = os.getenv(key)
        if not current or not current.strip().startswith("sm://"):
            continue
        resolved = resolve_secret_ref(current)
        if resolved is not None:
            os.environ[key] = resolved
