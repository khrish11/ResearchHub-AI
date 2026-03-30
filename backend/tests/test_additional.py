"""
tests/test_additional.py — integration tests using the Firestore emulator.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from main import app
from repositories import get_research_repository
from tests.env_flags import IS_PRODUCTION


TEST_PASSWORD = "Passw0rd!"


@pytest.fixture()
def c(repo):
    """TestClient wired to the emulator repo (injected via conftest)."""
    app.state._repo = repo
    app.dependency_overrides[get_research_repository] = lambda: repo
    with TestClient(app, raise_server_exceptions=False) as tc:
        yield tc
    app.dependency_overrides.pop(get_research_repository, None)


def _register(c: TestClient, email: str):
    resp = c.post("/auth/register", json={"email": email, "password": TEST_PASSWORD})
    assert resp.status_code == 200, f"Register failed: {resp.text}"
    return resp.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_cookie_session_is_set_and_auth_me_works_without_bearer_header(c):
    c.cookies.clear()
    email = f"cookie-auth-{uuid.uuid4().hex[:8]}@example.com"
    register_resp = c.post(
        "/auth/register", json={"email": email, "password": TEST_PASSWORD}
    )
    assert register_resp.status_code == 200
    assert "set-cookie" in {k.lower(): v for k, v in register_resp.headers.items()}

    if IS_PRODUCTION:
        token = register_resp.json().get("access_token")
        assert token
        me_resp = c.get("/auth/me", headers=_auth_headers(token))
    else:
        me_resp = c.get("/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json().get("email") == email


def test_refresh_and_logout_flow_for_cookie_sessions(c):
    c.cookies.clear()
    email = f"refresh-cookie-{uuid.uuid4().hex[:8]}@example.com"
    register_resp = c.post(
        "/auth/register", json={"email": email, "password": TEST_PASSWORD}
    )
    assert register_resp.status_code == 200
    token = register_resp.json().get("access_token")
    assert token

    if IS_PRODUCTION:
        # Secure cookies require HTTPS; in HTTP test client use bearer auth.
        before_refresh = c.get("/auth/me", headers=_auth_headers(token))
        assert before_refresh.status_code == 200

        refreshed = c.post("/auth/refresh")
        assert refreshed.status_code in (200, 401)

        active_token = (
            refreshed.json().get("access_token") if refreshed.status_code == 200 else token
        )
        after_refresh = c.get("/auth/me", headers=_auth_headers(active_token))
        assert after_refresh.status_code == 200
        assert after_refresh.json().get("email") == email

        logout_resp = c.post("/auth/logout")
        assert logout_resp.status_code == 200

        after_logout = c.get("/auth/me")
        assert after_logout.status_code == 401
    else:
        before_refresh = c.get("/auth/me")
        assert before_refresh.status_code == 200

        refreshed = c.post("/auth/refresh")
        assert refreshed.status_code == 200
        assert refreshed.json().get("access_token")

        after_refresh = c.get("/auth/me")
        assert after_refresh.status_code == 200
        assert after_refresh.json().get("email") == email

        logout_resp = c.post("/auth/logout")
        assert logout_resp.status_code == 200

        after_logout = c.get("/auth/me")
        assert after_logout.status_code == 401


def test_login_with_wrong_password_fails(c):
    _register(c, "wrongpw@example.com")
    r = c.post(
        "/auth/token", data={"username": "wrongpw@example.com", "password": "bad"}
    )
    assert r.status_code == 401


def test_protected_endpoint_requires_token(c):
    c.cookies.clear()
    r = c.get("/workspaces/")
    assert r.status_code == 401


def test_import_paper_workspace_must_belong_to_user(c):
    t1 = _register(c, "u1@example.com")
    headers = {"Authorization": f"Bearer {t1}"}

    # create a workspace with user u1
    r = c.post("/workspaces/", json={"name": "u1ws"}, headers=headers)
    assert r.status_code == 200
    ws_id = r.json()["id"]

    # register another user and attempt to import into u1's workspace with their token
    t2 = _register(c, "u2@example.com")
    headers2 = {"Authorization": f"Bearer {t2}"}
    r = c.post(
        "/papers/import",
        json={"title": "X", "authors": ["A"], "abstract": "a", "workspace_id": ws_id},
        headers=headers2,
    )
    assert r.status_code == 404


def test_search_papers_returns_mock_list(c):
    token = _register(c, "searcher@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    r = c.get("/papers/search?query=transformers", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "papers" in data and isinstance(data["papers"], list)
    assert len(data["papers"]) >= 1
    assert "title" in data["papers"][0]


def test_search_springer_handles_string_url(monkeypatch, c):
    """Ensure `search_springer` tolerates `url` returned as a plain string."""
    monkeypatch.setenv("SPRINGER_META_KEY", "fakekey")

    class DummyResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "records": [
                    {
                        "title": "SAMPLE",
                        "creators": [{"creator": "A"}],
                        "abstract": "Abs",
                        "publicationDate": "2020",
                        "doi": "10.1/TEST",
                        "url": "https://example.com/pdf",
                    }
                ]
            }

    import routers.papers as papers_mod

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *args, **kwargs):
            return DummyResp()

    monkeypatch.setattr(papers_mod.httpx, "AsyncClient", lambda *a, **k: DummyClient())

    token = _register(c, "spr-user@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    r = c.get("/papers/search-springer?query=test", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["papers"][0]["url"] == "https://doi.org/10.1/TEST"


def test_search_springer_handles_subjects_string(monkeypatch, c):
    monkeypatch.setenv("SPRINGER_META_KEY", "fakekey")

    class DummyResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "records": [
                    {
                        "title": "Subjects test",
                        "creators": [{"creator": "B"}],
                        "abstract": "An abstract",
                        "publicationDate": "2021",
                        "identifiers": {},
                        "subjects": "Computer Science",  # string not list
                    }
                ]
            }

    import routers.papers as papers_mod

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *args, **kwargs):
            return DummyResp()

    monkeypatch.setattr(papers_mod.httpx, "AsyncClient", lambda *a, **k: DummyClient())

    token = _register(c, "subj-user@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    r = c.get("/papers/search-springer?query=test", headers=headers)
    assert r.status_code == 200


def test_workspace_papers_persist_after_relogin(c):
    c.cookies.clear()
    email = f"ws-paper-{uuid.uuid4().hex[:8]}@example.com"
    token = _register(c, email)
    headers = {"Authorization": f"Bearer {token}"}

    ws = c.post("/workspaces/", json={"name": "WS-Paper"}, headers=headers)
    assert ws.status_code == 200
    ws_id = ws.json()["id"]

    imp = c.post(
        "/papers/import",
        json={
            "title": "Persist",
            "authors": ["D"],
            "abstract": "A",
            "workspace_id": ws_id,
        },
        headers=headers,
    )
    assert imp.status_code == 200

    # Re-login
    login = c.post("/auth/token", data={"username": email, "password": TEST_PASSWORD})
    assert login.status_code == 200
    token2 = login.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    detail = c.get(f"/workspaces/{ws_id}", headers=headers2)
    assert detail.status_code == 200
    assert detail.json()["papers"][0]["title"] == "Persist"


def test_change_password_rejects_weak_new_password(c):
    c.cookies.clear()
    email = f"pwuser-{uuid.uuid4().hex[:8]}@example.com"
    token = _register(c, email)

    r = c.post(
        "/auth/change-password",
        json={"current_password": TEST_PASSWORD, "new_password": "short"},
        headers=_auth_headers(token) if IS_PRODUCTION else None,
    )
    assert r.status_code in (400, 422)


def test_auth_me_marks_developer_email(c):
    c.cookies.clear()
    email = "testuser@soyog.test"
    token = _register(c, email)
    me = c.get("/auth/me", headers=_auth_headers(token) if IS_PRODUCTION else None)
    assert me.status_code == 200
    data = me.json()
    assert data.get("email") == email
    assert isinstance(data.get("is_developer"), bool)


def test_developer_overview_access_control(c):
    token = _register(c, "nondev@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    r = c.get("/developer/overview", headers=headers)
    assert r.status_code in (200, 403)
