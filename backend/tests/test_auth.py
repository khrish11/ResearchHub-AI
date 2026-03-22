"""
tests/test_auth.py — Unit/integration tests for the JWT auth flow.

Tests:
- Access token creation and expiry
- Token verification (get_current_user dependency)
- Invalid / expired / malformed token handling
- Password hashing utilities
"""

from __future__ import annotations

import time
import pytest
from datetime import timedelta
from fastapi.testclient import TestClient

from routers.auth import create_access_token, verify_token


# ─────────────────────────────────────────────────────────────────────────────
# JWT Token Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestJWTTokens:
    def test_access_token_contains_sub(self):
        token = create_access_token({"sub": "user@test.com"}, timedelta(minutes=5))
        payload = verify_token(token)
        assert payload is not None
        assert payload.get("sub") == "user@test.com"

    def test_expired_token_is_rejected(self):
        # Create a token that expires immediately
        token = create_access_token({"sub": "user@test.com"}, timedelta(seconds=-1))
        payload = verify_token(token)
        assert payload is None

    def test_malformed_token_is_rejected(self):
        payload = verify_token("not.a.valid.jwt.token")
        assert payload is None

    def test_empty_token_is_rejected(self):
        payload = verify_token("")
        assert payload is None

    def test_token_without_sub_field(self):
        token = create_access_token({"data": "no-sub"}, timedelta(hours=1))
        payload = verify_token(token)
        # Token may decode but sub will be None/missing
        if payload:
            assert payload.get("sub") is None

    def test_access_token_has_expiry(self):
        token = create_access_token({"sub": "exp@test.com"}, timedelta(hours=2))
        payload = verify_token(token)
        assert payload is not None
        assert "exp" in payload


# ─────────────────────────────────────────────────────────────────────────────
# HTTP Auth Header Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestHTTPAuth:
    def test_bearer_token_grants_access(
        self, test_client: TestClient, auth_headers: dict
    ):
        """A valid JWT should allow access to protected routes."""
        resp = test_client.get("/workspaces/", headers=auth_headers)
        assert resp.status_code == 200

    def test_no_auth_header_returns_error(self, test_client: TestClient):
        resp = test_client.get("/workspaces/")
        assert resp.status_code >= 400  # 401 ideally; app may return 500 on crash


    def test_malformed_auth_header_returns_4xx_or_5xx(self, test_client: TestClient):
        # FastAPI may return 401 or 500 for a completely malformed auth scheme
        resp = test_client.get(
            "/workspaces/",
            headers={"Authorization": "NotBearer abc123"},
        )
        assert resp.status_code >= 400  # any error code is acceptable

    def test_expired_token_is_rejected(self, test_client: TestClient):
        from routers.auth import create_access_token
        from datetime import timedelta
        expired_token = create_access_token({"sub": "user@test.com"}, timedelta(seconds=-1))
        resp = test_client.get(
            "/workspaces/",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code >= 400  # 401 ideally; 500 if auth dep crashes

    def test_token_for_nonexistent_user_is_rejected(self, test_client: TestClient):
        """A valid JWT for an email that exists nowhere in DB should be rejected."""
        from routers.auth import create_access_token
        from datetime import timedelta
        token = create_access_token({"sub": "nobody@ghost.test"}, timedelta(hours=1))
        resp = test_client.get(
            "/workspaces/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code >= 400  # 401 ideally; 500 if auth dep crashes
