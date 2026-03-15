import os
import sys
from pathlib import Path

# Use a unique temporary DB for these tests to avoid collisions with any
# running backend instances or parallel test runs.
import uuid
TEST_DB_PATH = os.path.join(os.path.dirname(__file__), f"test_temp_{uuid.uuid4().hex}.db")
os.environ['DATABASE_URL'] = f'sqlite:///{TEST_DB_PATH}'

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
import main

client = TestClient(main.app)
TEST_PASSWORD = "Passw0rd!"


def register(email: str):
    r = client.post('/auth/register', json={'email': email, 'password': TEST_PASSWORD})
    assert r.status_code == 200
    return r.json()['access_token']


def test_cookie_session_is_set_and_auth_me_works_without_bearer_header():
    client.cookies.clear()
    email = f"cookie-auth-{uuid.uuid4().hex[:8]}@example.com"
    register_resp = client.post('/auth/register', json={'email': email, 'password': TEST_PASSWORD})
    assert register_resp.status_code == 200
    assert 'set-cookie' in {k.lower(): v for k, v in register_resp.headers.items()}

    me_resp = client.get('/auth/me')
    assert me_resp.status_code == 200
    assert me_resp.json().get('email') == email


def test_refresh_and_logout_flow_for_cookie_sessions():
    client.cookies.clear()
    email = f"refresh-cookie-{uuid.uuid4().hex[:8]}@example.com"
    register_resp = client.post('/auth/register', json={'email': email, 'password': TEST_PASSWORD})
    assert register_resp.status_code == 200

    before_refresh = client.get('/auth/me')
    assert before_refresh.status_code == 200

    refreshed = client.post('/auth/refresh')
    assert refreshed.status_code == 200
    assert refreshed.json().get('access_token')

    after_refresh = client.get('/auth/me')
    assert after_refresh.status_code == 200
    assert after_refresh.json().get('email') == email

    logout_resp = client.post('/auth/logout')
    assert logout_resp.status_code == 200

    after_logout = client.get('/auth/me')
    assert after_logout.status_code == 401


def test_login_with_wrong_password_fails():
    token = register('wrongpw@example.com')
    # login with wrong password should return 401
    r = client.post('/auth/token', data={'username': 'wrongpw@example.com', 'password': 'bad'})
    assert r.status_code == 401


def test_protected_endpoint_requires_token():
    client.cookies.clear()
    r = client.get('/workspaces/')
    assert r.status_code == 401


def test_import_paper_workspace_must_belong_to_user():
    t1 = register('u1@example.com')
    headers = {'Authorization': f'Bearer {t1}'}

    # create a workspace with user u1
    r = client.post('/workspaces/', json={'name': 'u1ws'}, headers=headers)
    assert r.status_code == 200
    ws_id = r.json()['id']

    # register another user and attempt to import into u1's workspace with their token
    t2 = register('u2@example.com')
    headers2 = {'Authorization': f'Bearer {t2}'}
    r = client.post('/papers/import', json={'title': 'X', 'authors': ['A'], 'abstract': 'a', 'workspace_id': ws_id}, headers=headers2)
    assert r.status_code == 404


def test_search_papers_returns_mock_list():
    token = register('searcher@example.com')
    headers = {'Authorization': f'Bearer {token}'}
    r = client.get('/papers/search?query=transformers', headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert 'papers' in data and isinstance(data['papers'], list)
    assert len(data['papers']) >= 1
    assert 'title' in data['papers'][0]


def test_search_springer_handles_string_url(monkeypatch):
    """Ensure `search_springer` tolerates `url` returned as a plain string."""
    monkeypatch.setenv('SPRINGER_META_KEY', 'fakekey')

    class DummyResp:
        status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return {
                'records': [
                    {
                        'title': 'SAMPLE',
                        'creators': [{'creator': 'A'}],
                        'abstract': 'Abs',
                        'publicationDate': '2020-01-01',
                        'doi': '10.1/example',
                        'url': 'https://example.com/article',
                        'subjects': [],
                        'publicationName': 'J Test'
                    }
                ]
            }

    class DummyClient:
        def __init__(self, *a, **k):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def get(self, *args, **kwargs):
            return DummyResp()

    monkeypatch.setattr('routers.papers.httpx.AsyncClient', DummyClient)

    token = register(f"spr-search-{uuid.uuid4().hex[:6]}@example.com")
    headers = {'Authorization': f'Bearer {token}'}
    r = client.get('/papers/search-springer', params={'query': 'gene', 'max_results': 1}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    # DOI is preferred when present
    assert data['papers'] and data['papers'][0]['url'] == 'https://doi.org/10.1/example'


def test_search_springer_handles_subjects_string(monkeypatch):
    """Ensure `search_springer` tolerates `subjects` returned as a string."""
    monkeypatch.setenv('SPRINGER_META_KEY', 'fakekey')

    class DummyResp2:
        status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return {
                'records': [
                    {
                        'title': 'SAMPLE2',
                        'creators': [{'creator': 'B'}],
                        'abstract': 'Abs2',
                        'publicationDate': '2021-02-02',
                        'doi': '',
                        'url': [{'value': 'https://example.com/2'}],
                        'subjects': 'Genetics',
                        'publicationName': 'J Test 2'
                    }
                ]
            }

    class DummyClient2:
        def __init__(self, *a, **k):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def get(self, *args, **kwargs):
            return DummyResp2()

    monkeypatch.setattr('routers.papers.httpx.AsyncClient', DummyClient2)

    token = register(f"spr-search2-{uuid.uuid4().hex[:6]}@example.com")
    headers = {'Authorization': f'Bearer {token}'}
    r = client.get('/papers/search-springer', params={'query': 'gene', 'max_results': 1}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data['papers'] and ('Genetics' in data['papers'][0].get('categories', []) or 'Genetics' in data['papers'][0].get('publication_name', ''))


def test_workspace_papers_persist_after_relogin():
    email = f"persist-{uuid.uuid4().hex[:8]}@example.com"
    password = TEST_PASSWORD

    register_resp = client.post('/auth/register', json={'email': email, 'password': password})
    assert register_resp.status_code == 200
    token = register_resp.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    ws_resp = client.post('/workspaces/default', headers=headers)
    assert ws_resp.status_code == 200
    workspace_id = ws_resp.json()['id']

    import_resp = client.post(
        '/papers/import',
        json={
            'title': 'Persistence Test Paper',
            'authors': ['Author One'],
            'abstract': 'This paper validates persistence across logout/login cycles.',
            'workspace_id': workspace_id,
        },
        headers=headers,
    )
    assert import_resp.status_code == 200

    relogin_resp = client.post('/auth/token', data={'username': email, 'password': password})
    assert relogin_resp.status_code == 200
    new_token = relogin_resp.json()['access_token']
    relogin_headers = {'Authorization': f'Bearer {new_token}'}

    ws_list_resp = client.get('/workspaces/', headers=relogin_headers)
    assert ws_list_resp.status_code == 200
    workspace_ids = [item['id'] for item in ws_list_resp.json()]
    assert workspace_id in workspace_ids

    ws_detail_resp = client.get(f'/workspaces/{workspace_id}', headers=relogin_headers)
    assert ws_detail_resp.status_code == 200
    papers = ws_detail_resp.json().get('papers', [])
    assert any((paper.get('title') or '').strip() == 'Persistence Test Paper' for paper in papers)


def test_change_password_rejects_weak_new_password():
    email = f"weak-change-{uuid.uuid4().hex[:8]}@example.com"
    token = register(email)
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.post(
        '/auth/change-password',
        json={'current_password': TEST_PASSWORD, 'new_password': 'short'},
        headers=headers,
    )
    assert resp.status_code == 400
    assert 'Password' in resp.json().get('detail', '')


def test_auth_me_marks_developer_email(monkeypatch):
    dev_email = f"dev-{uuid.uuid4().hex[:6]}@example.com"
    monkeypatch.setenv('DEVELOPER_EMAILS', dev_email)

    token = register(dev_email)
    headers = {'Authorization': f'Bearer {token}'}
    r = client.get('/auth/me', headers=headers)
    assert r.status_code == 200
    assert r.json().get('is_developer') is True


def test_developer_overview_access_control(monkeypatch):
    # non-developer should be denied when local bypass is disabled
    monkeypatch.delenv('DEVELOPER_EMAILS', raising=False)
    monkeypatch.setenv('ALLOW_DEV_PANEL', '0')
    monkeypatch.setenv('APP_ENV', 'production')
    non_dev = f"user-{uuid.uuid4().hex[:6]}@example.com"
    token_non_dev = register(non_dev)
    headers_non_dev = {'Authorization': f'Bearer {token_non_dev}'}
    denied = client.get('/developer/overview', headers=headers_non_dev)
    assert denied.status_code == 403

    # developer email should be granted
    dev_email = f"dev-{uuid.uuid4().hex[:6]}@example.com"
    monkeypatch.setenv('DEVELOPER_EMAILS', dev_email)
    token_dev = register(dev_email)
    headers_dev = {'Authorization': f'Bearer {token_dev}'}
    allowed = client.get('/developer/overview', headers=headers_dev)
    assert allowed.status_code == 200
    payload = allowed.json()
    assert 'summary' in payload and 'users' in payload['summary']
