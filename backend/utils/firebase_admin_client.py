from __future__ import annotations

import os
import logging
from typing import Any, Optional

try:
    import firebase_admin
    from firebase_admin import app_check, auth, credentials
except Exception:  # pragma: no cover - optional dependency until configured
    firebase_admin = None
    app_check = None
    auth = None
    credentials = None

from utils.firebase_storage import _normalize_windows_env_path, storage_bucket_name
from utils.firebase_service_account import load_service_account_info_from_env


_APP = None
logger = logging.getLogger(__name__)


def firebase_admin_is_configured() -> bool:
    return bool(
        (os.getenv("FIREBASE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT"))
    )


def _make_emulator_credential():
    """
    Return a minimal fake credential that firebase-admin accepts for emulator use.
    The emulator doesn't validate auth tokens, so any token works.
    """
    from datetime import datetime, timedelta, timezone

    class _FakeCred:
        token = "owner"
        expiry = datetime.now(timezone.utc) + timedelta(hours=24)
        valid = True

        def refresh(self, request):
            pass

        def before_request(self, request, method, url, headers):
            headers["Authorization"] = f"Bearer {self.token}"

    return _FakeCred()


def get_firebase_admin_app():
    global _APP
    if _APP is not None:
        return _APP
    if firebase_admin is None or credentials is None:
        raise RuntimeError("firebase-admin is not installed.")

    # Emulator short-circuit: skip ADC entirely.
    # When FIRESTORE_EMULATOR_HOST is set, the Firestore emulator ignores
    # auth tokens completely.  We must not call ApplicationDefault() or
    # credentials.Certificate() because there are no real credentials in
    # the test / CI environment.
    if os.getenv("FIRESTORE_EMULATOR_HOST"):
        try:
            _APP = firebase_admin.get_app()
            return _APP
        except ValueError:
            pass
        project_id = (
            os.getenv("FIREBASE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or "demo-test"
        ).strip()
        _APP = firebase_admin.initialize_app(
            credential=None,
            options={"projectId": project_id},
        )
        return _APP
    # Production / staging path.

    service_account_info = load_service_account_info_from_env()
    cert_path = _normalize_windows_env_path(
        os.getenv("FIREBASE_CREDENTIALS_PATH")
    ) or _normalize_windows_env_path(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
    if cert_path and not os.path.isfile(cert_path):
        logger.warning(
            "Configured Firebase credentials file does not exist (%s); falling back to Application Default Credentials.",
            cert_path,
        )
        cert_path = None
    options: dict[str, Any] = {}
    project_id = (
        os.getenv("FIREBASE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or ""
    ).strip()
    if not project_id and service_account_info:
        project_id = str(service_account_info.get("project_id") or "").strip()
    bucket_name = storage_bucket_name()
    if project_id:
        options["projectId"] = project_id
    if bucket_name:
        options["storageBucket"] = bucket_name

    try:
        _APP = firebase_admin.get_app()
        return _APP
    except ValueError:
        pass

    if service_account_info:
        cred = credentials.Certificate(service_account_info)
    elif cert_path:
        cred = credentials.Certificate(cert_path)
    else:
        cred = credentials.ApplicationDefault()
    _APP = firebase_admin.initialize_app(cred, options=options or None)
    return _APP



def verify_firebase_id_token(id_token: str) -> dict[str, Any]:
    if auth is None:
        raise RuntimeError("firebase-admin auth support is unavailable.")
    app = get_firebase_admin_app()
    # Allow up to 10 seconds of clock skew to handle minor system time drift
    # between the client (browser) and the server.
    return auth.verify_id_token(id_token, app=app, clock_skew_seconds=10)


def revoke_firebase_refresh_tokens(uid: str) -> None:
    if auth is None:
        return
    app = get_firebase_admin_app()
    auth.revoke_refresh_tokens(uid, app=app)


def verify_firebase_app_check_token(token: str) -> dict[str, Any]:
    if app_check is None:
        raise RuntimeError("firebase-admin app check support is unavailable.")
    get_firebase_admin_app()
    return app_check.verify_token(token)


def firebase_sign_in_provider(decoded_token: dict[str, Any]) -> Optional[str]:
    firebase_meta = decoded_token.get("firebase") or {}
    provider = firebase_meta.get("sign_in_provider")
    return str(provider).strip() or None
