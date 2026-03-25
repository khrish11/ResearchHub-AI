from __future__ import annotations

import mimetypes
import os
import logging
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, Optional

from google.cloud import storage
from google.oauth2 import service_account


_ENV_ESCAPE_REVERSE = {
    "\a": "a",
    "\b": "b",
    "\f": "f",
    "\n": "n",
    "\r": "r",
    "\t": "t",
    "\v": "v",
}
logger = logging.getLogger(__name__)


def _normalize_windows_env_path(raw_value: str | None) -> str | None:
    value = (raw_value or "").strip().strip('"').strip("'")
    if not value:
        return None
    rebuilt: list[str] = []
    for ch in value:
        if ch in _ENV_ESCAPE_REVERSE:
            rebuilt.append("\\" + _ENV_ESCAPE_REVERSE[ch])
        else:
            rebuilt.append(ch)
    normalized = "".join(rebuilt)
    if len(normalized) > 2 and normalized[1] == ":":
        normalized = normalized.replace("\\", "/")
    return normalized


def _firebase_project_id() -> str | None:
    return (os.getenv("FIREBASE_PROJECT_ID") or "").strip() or None


def _credentials_path() -> str | None:
    path = (
        _normalize_windows_env_path(os.getenv("FIREBASE_CREDENTIALS_PATH"))
        or _normalize_windows_env_path(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
        or None
    )
    if path and not os.path.isfile(path):
        logger.warning(
            "Configured Firebase Storage credentials file does not exist (%s); falling back to Application Default Credentials.",
            path,
        )
        return None
    return path


def storage_bucket_name() -> str | None:
    explicit = (os.getenv("FIREBASE_STORAGE_BUCKET") or "").strip()
    if explicit:
        return explicit
    project_id = _firebase_project_id()
    if project_id:
        return f"{project_id}.firebasestorage.app"
    return None


def storage_is_configured() -> bool:
    return bool(storage_bucket_name())


_STORAGE_CLIENT = None
_STORAGE_LOCK = Lock()


def _storage_client() -> storage.Client:
    global _STORAGE_CLIENT
    with _STORAGE_LOCK:
        if _STORAGE_CLIENT is not None:
            return _STORAGE_CLIENT
        client_kwargs: Dict[str, Any] = {}
        project_id = _firebase_project_id()
        if project_id:
            client_kwargs["project"] = project_id
        credentials_path = _credentials_path()
        if credentials_path:
            client_kwargs["credentials"] = service_account.Credentials.from_service_account_file(
                credentials_path,
            )
        _STORAGE_CLIENT = storage.Client(**client_kwargs)
        return _STORAGE_CLIENT


@dataclass
class UploadedStorageObject:
    bucket: str
    path: str
    gs_url: str
    content_type: str
    size_bytes: int


def upload_bytes(
    *,
    storage_path: str,
    data: bytes,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> UploadedStorageObject:
    bucket_name = storage_bucket_name()
    if not bucket_name:
        raise RuntimeError("FIREBASE_STORAGE_BUCKET or FIREBASE_PROJECT_ID must be configured.")
    client = _storage_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(storage_path)
    blob.metadata = metadata or None
    resolved_type = content_type or mimetypes.guess_type(storage_path)[0] or "application/octet-stream"
    blob.upload_from_string(data, content_type=resolved_type)
    return UploadedStorageObject(
        bucket=bucket_name,
        path=storage_path,
        gs_url=f"gs://{bucket_name}/{storage_path}",
        content_type=resolved_type,
        size_bytes=len(data),
    )


@dataclass
class DownloadedStorageObject:
    data: bytes
    content_type: str
    filename: Optional[str] = None


def download_bytes(*, storage_path: str) -> DownloadedStorageObject:
    bucket_name = storage_bucket_name()
    if not bucket_name:
        raise RuntimeError("FIREBASE_STORAGE_BUCKET or FIREBASE_PROJECT_ID must be configured.")
    client = _storage_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(storage_path)
    data = blob.download_as_bytes()
    content_type = blob.content_type or mimetypes.guess_type(storage_path)[0] or "application/octet-stream"
    filename = storage_path.split("/")[-1] if "/" in storage_path else storage_path
    return DownloadedStorageObject(data=data, content_type=content_type, filename=filename)
