from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


def _strip_optional_assignment(raw: str, key_name: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return value

    prefix = f"{key_name}="
    if value.startswith(prefix):
        value = value[len(prefix) :].strip()

    # tolerate accidentally quoted values in env UIs
    if (
        len(value) >= 2
        and ((value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'"))
    ):
        value = value[1:-1].strip()

    return value


def _normalize_private_key(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return raw
    # Render env text usually stores multiline keys as escaped "\n".
    return raw.replace("\\n", "\n")


def _validate_service_account_info(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    project_id = str(payload.get("project_id") or "").strip()
    client_email = str(payload.get("client_email") or "").strip()
    private_key = _normalize_private_key(str(payload.get("private_key") or ""))
    if not project_id or not client_email or not private_key:
        return None

    normalized = dict(payload)
    normalized["type"] = str(normalized.get("type") or "service_account")
    normalized["project_id"] = project_id
    normalized["client_email"] = client_email
    normalized["private_key"] = private_key
    normalized["token_uri"] = str(
        normalized.get("token_uri") or "https://oauth2.googleapis.com/token"
    )
    normalized["auth_uri"] = str(
        normalized.get("auth_uri") or "https://accounts.google.com/o/oauth2/auth"
    )
    normalized["auth_provider_x509_cert_url"] = str(
        normalized.get("auth_provider_x509_cert_url")
        or "https://www.googleapis.com/oauth2/v1/certs"
    )
    return normalized


def _load_service_account_json(raw: str, *, source_name: str) -> Optional[Dict[str, Any]]:
    try:
        parsed = json.loads(raw)
    except Exception:
        logger.warning(
            "Invalid %s content; expected JSON object. Falling back to other credential sources.",
            source_name,
        )
        return None
    if not isinstance(parsed, dict):
        logger.warning(
            "Invalid %s content; expected JSON object. Falling back to other credential sources.",
            source_name,
        )
        return None
    normalized = _validate_service_account_info(parsed)
    if normalized is None:
        logger.warning(
            "%s is missing required service account fields (project_id/client_email/private_key).",
            source_name,
        )
    return normalized


def _load_service_account_json_base64(raw: str) -> Optional[Dict[str, Any]]:
    compact = "".join(str(raw or "").split())
    if not compact:
        return None
    padded = compact + ("=" * (-len(compact) % 4))
    try:
        decoded = base64.b64decode(padded.encode("utf-8"), validate=False).decode(
            "utf-8"
        )
    except Exception:
        logger.warning(
            "Invalid FIREBASE_SERVICE_ACCOUNT_JSON_BASE64 value; expected base64 JSON."
        )
        return None
    return _load_service_account_json(
        decoded, source_name="FIREBASE_SERVICE_ACCOUNT_JSON_BASE64"
    )


def _load_split_service_account_env() -> Optional[Dict[str, Any]]:
    project_id = str(os.getenv("FIREBASE_SERVICE_ACCOUNT_PROJECT_ID") or "").strip()
    client_email = str(os.getenv("FIREBASE_SERVICE_ACCOUNT_CLIENT_EMAIL") or "").strip()
    private_key = _normalize_private_key(
        str(os.getenv("FIREBASE_SERVICE_ACCOUNT_PRIVATE_KEY") or "")
    )
    if not project_id or not client_email or not private_key:
        return None
    payload: Dict[str, Any] = {
        "type": "service_account",
        "project_id": project_id,
        "client_email": client_email,
        "private_key": private_key,
        "private_key_id": str(
            os.getenv("FIREBASE_SERVICE_ACCOUNT_PRIVATE_KEY_ID") or ""
        ).strip(),
        "client_id": str(os.getenv("FIREBASE_SERVICE_ACCOUNT_CLIENT_ID") or "").strip(),
        "token_uri": str(
            os.getenv("FIREBASE_SERVICE_ACCOUNT_TOKEN_URI")
            or "https://oauth2.googleapis.com/token"
        ).strip(),
        "auth_uri": str(
            os.getenv("FIREBASE_SERVICE_ACCOUNT_AUTH_URI")
            or "https://accounts.google.com/o/oauth2/auth"
        ).strip(),
        "auth_provider_x509_cert_url": str(
            os.getenv("FIREBASE_SERVICE_ACCOUNT_AUTH_PROVIDER_X509_CERT_URL")
            or "https://www.googleapis.com/oauth2/v1/certs"
        ).strip(),
        "client_x509_cert_url": str(
            os.getenv("FIREBASE_SERVICE_ACCOUNT_CLIENT_X509_CERT_URL") or ""
        ).strip(),
        "universe_domain": str(
            os.getenv("FIREBASE_SERVICE_ACCOUNT_UNIVERSE_DOMAIN")
            or "googleapis.com"
        ).strip(),
    }
    return _validate_service_account_info(payload)


def load_service_account_info_from_env() -> Optional[Dict[str, Any]]:
    """
    Resolve Firebase service account credentials from environment variables.

    Resolution order:
    1) FIREBASE_SERVICE_ACCOUNT_JSON_BASE64
    2) FIREBASE_SERVICE_ACCOUNT_JSON
    3) split FIREBASE_SERVICE_ACCOUNT_* fields
    """
    encoded = _strip_optional_assignment(
        os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON_BASE64") or "",
        "FIREBASE_SERVICE_ACCOUNT_JSON_BASE64",
    )
    logger.info(f"Service account: FIREBASE_SERVICE_ACCOUNT_JSON_BASE64 length={len(encoded)}")
    if encoded:
        resolved = _load_service_account_json_base64(encoded)
        logger.info(f"Service account: base64 resolved={resolved is not None}")
        if resolved is not None:
            return resolved

    raw_json = _strip_optional_assignment(
        os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON") or "",
        "FIREBASE_SERVICE_ACCOUNT_JSON",
    )
    logger.info(f"Service account: FIREBASE_SERVICE_ACCOUNT_JSON length={len(raw_json)}")
    if raw_json:
        resolved = _load_service_account_json(
            raw_json, source_name="FIREBASE_SERVICE_ACCOUNT_JSON"
        )
        logger.info(f"Service account: json resolved={resolved is not None}")
        if resolved is not None:
            return resolved

    resolved = _load_split_service_account_env()
    logger.info(f"Service account: split fields resolved={resolved is not None}")
    return resolved
