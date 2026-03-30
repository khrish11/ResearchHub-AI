"""
tests/test_endpoints.py — Integration tests for FastAPI HTTP endpoints.

Uses the real FastAPI `test_client` fixture (see conftest.py) which is wired
to the Firebase Emulator. Auth is handled via JWT tokens created in conftest.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.env_flags import ALLOWED_FRONTEND_ORIGIN, IS_PRODUCTION


# ─────────────────────────────────────────────────────────────────────────────
# Health & Info endpoints
# ─────────────────────────────────────────────────────────────────────────────


class TestHealthEndpoints:
    def test_health_live(self, test_client: TestClient):
        resp = test_client.get("/health/live")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") in {"ok", "alive"}

    def test_health_ready_returns_json(self, test_client: TestClient):
        resp = test_client.get("/health/ready")
        # May return 200 or 503 depending on whether emulator responds in time
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "status" in data


# ─────────────────────────────────────────────────────────────────────────────
# Authentication endpoints
# ─────────────────────────────────────────────────────────────────────────────


class TestAuthEndpoints:
    def test_register_new_user(self, test_client: TestClient):
        resp = test_client.post(
            "/auth/register",
            json={"email": "newreg@soyog.test", "password": "StrongPass123!"},
        )
        # 201 Created or 200 OK depending on implementation
        assert resp.status_code in (200, 201, 409)  # 409 if email exists

    def test_login_with_wrong_password_returns_401(self, test_client: TestClient):
        test_client.post(
            "/auth/register",
            json={"email": "badpass@soyog.test", "password": "RealPass999!"},
        )
        resp = test_client.post(
            "/auth/token",
            data={"username": "badpass@soyog.test", "password": "WrongPass"},
        )
        assert resp.status_code in (401, 422)

    def test_login_nonexistent_user_returns_401_or_404(self, test_client: TestClient):
        resp = test_client.post(
            "/auth/login",
            json={"email": "ghost@soyog.test", "password": "anypassword"},
        )
        assert resp.status_code in (401, 404, 422)

    def test_protected_route_without_token_returns_401(self, test_client: TestClient):
        resp = test_client.get("/workspaces/")
        assert resp.status_code == 401
        data = resp.json()
        assert isinstance(data.get("error_code"), str)
        assert isinstance(data.get("message"), str)
        assert isinstance(data.get("details"), dict)

    def test_protected_route_with_invalid_token_returns_401(
        self, test_client: TestClient
    ):
        resp = test_client.get(
            "/workspaces/",
            headers={"Authorization": "Bearer totally.invalid.token"},
        )
        assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# Workspace endpoints
# ─────────────────────────────────────────────────────────────────────────────


class TestWorkspaceEndpoints:
    def test_list_workspaces_authenticated(
        self, test_client: TestClient, auth_headers: dict
    ):
        resp = test_client.get("/workspaces/", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_workspace(self, test_client: TestClient, auth_headers: dict):
        resp = test_client.post(
            "/workspaces/",
            json={"name": "Test Workspace", "description": "Created in test"},
            headers=auth_headers,
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data.get("name") == "Test Workspace"

    def test_create_then_list_workspace(
        self, test_client: TestClient, auth_headers: dict
    ):
        test_client.post(
            "/workspaces/",
            json={"name": "Listed WS"},
            headers=auth_headers,
        )
        resp = test_client.get("/workspaces/", headers=auth_headers)
        names = [ws["name"] for ws in resp.json()]
        assert "Listed WS" in names

    def test_delete_workspace(self, test_client: TestClient, auth_headers: dict):
        create_resp = test_client.post(
            "/workspaces/",
            json={"name": "To Delete WS"},
            headers=auth_headers,
        )
        ws_id = create_resp.json()["id"]
        del_resp = test_client.delete(f"/workspaces/{ws_id}", headers=auth_headers)
        assert del_resp.status_code in (200, 204)

    def test_delete_nonexistent_workspace_returns_404(
        self, test_client: TestClient, auth_headers: dict
    ):
        resp = test_client.delete("/workspaces/999999", headers=auth_headers)
        assert resp.status_code == 404

    def test_workspace_not_accessible_by_other_user(
        self, test_client: TestClient, auth_headers: dict
    ):
        """A workspace created by user A should not be accessible by user B."""
        create_resp = test_client.post(
            "/workspaces/",
            json={"name": "Private WS"},
            headers=auth_headers,
        )
        ws_id = create_resp.json()["id"]

        # Register user B
        test_client.post(
            "/auth/register",
            json={"email": "userb@soyog.test", "password": "UserBPass123!"},
        )
        from routers.auth import create_access_token
        from datetime import timedelta

        token_b = create_access_token({"sub": "userb@soyog.test"}, timedelta(hours=1))
        headers_b = {"Authorization": f"Bearer {token_b}"}

        resp = test_client.get(f"/workspaces/{ws_id}", headers=headers_b)
        assert resp.status_code in (403, 404)


# ─────────────────────────────────────────────────────────────────────────────
# Paper endpoints
# ─────────────────────────────────────────────────────────────────────────────


class TestPaperEndpoints:
    def _create_workspace(self, test_client: TestClient, auth_headers: dict) -> int:
        resp = test_client.post(
            "/workspaces/",
            json={"name": "Paper WS"},
            headers=auth_headers,
        )
        return resp.json()["id"]

    def test_list_papers_empty_workspace(
        self, test_client: TestClient, auth_headers: dict
    ):
        ws_id = self._create_workspace(test_client, auth_headers)
        resp = test_client.get(f"/workspaces/{ws_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["papers"] == []


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases & rate limiting
# ─────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_options_preflight_returns_200(self, test_client: TestClient):
        """CORS preflight should succeed."""
        origin = ALLOWED_FRONTEND_ORIGIN if IS_PRODUCTION else "http://localhost:5173"
        resp = test_client.options(
            "/workspaces/",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        if IS_PRODUCTION and origin != "http://localhost:5173":
            assert resp.status_code in (200, 204)
        elif IS_PRODUCTION:
            assert resp.status_code in (200, 204, 400)
        else:
            assert resp.status_code in (200, 204)

    def test_create_workspace_missing_name_returns_422(
        self, test_client: TestClient, auth_headers: dict
    ):
        resp = test_client.post(
            "/workspaces/",
            json={},  # missing required `name`
            headers=auth_headers,
        )
        assert resp.status_code == 422
        data = resp.json()
        assert data.get("error_code") == "VALIDATION_ERROR"
        assert isinstance(data.get("message"), str)
        assert isinstance(data.get("details"), dict)
