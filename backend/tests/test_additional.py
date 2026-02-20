import os

# Use a unique temporary DB for these tests to avoid collisions with any
# running backend instances or parallel test runs.
import uuid
TEST_DB_PATH = os.path.join(os.path.dirname(__file__), f"test_temp_{uuid.uuid4().hex}.db")
os.environ['DATABASE_URL'] = f'sqlite:///{TEST_DB_PATH}'

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