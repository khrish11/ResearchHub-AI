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


def register(email: str):
    r = client.post('/auth/register', json={'email': email, 'password': 'pw'})
    assert r.status_code == 200
    return r.json()['access_token']


def test_login_with_wrong_password_fails():
    token = register('wrongpw@example.com')
    # login with wrong password should return 401
    r = client.post('/auth/token', data={'username': 'wrongpw@example.com', 'password': 'bad'})
    assert r.status_code == 401


def test_protected_endpoint_requires_token():
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
