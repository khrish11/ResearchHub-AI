import os
# Use a unique temporary file-backed SQLite DB for tests so SQLAlchemy tables
# persist across threads used by TestClient and avoid collisions with running
# servers or other test runs.
import uuid
TEST_DB_PATH = os.path.join(os.path.dirname(__file__), f"test_temp_{uuid.uuid4().hex}.db")
os.environ['DATABASE_URL'] = f'sqlite:///{TEST_DB_PATH}'

from fastapi.testclient import TestClient
import main

client = TestClient(main.app)



def register_and_get_token(email: str):
    resp = client.post('/auth/register', json={'email': email, 'password': 'pw'})
    assert resp.status_code == 200
    return resp.json()['access_token']


def test_smoke_endpoints_work():
    token = register_and_get_token('t1@example.com')
    headers = {'Authorization': f'Bearer {token}'}

    # AI status (should be present)
    r = client.get('/ai/status')
    assert r.status_code == 200
    assert 'enabled' in r.json()

    # default workspace
    r = client.post('/workspaces/default', headers=headers)
    assert r.status_code == 200
    ws = r.json()
    assert 'id' in ws

    # create workspace
    r = client.post('/workspaces/', json={'name': 'WS1'}, headers=headers)
    assert r.status_code == 200

    # import paper
    r = client.post('/papers/import', json={'title': 'Paper1', 'authors': ['A'], 'abstract': 'A', 'workspace_id': ws['id']}, headers=headers)
    assert r.status_code == 200

    # get workspace detail
    r = client.get(f"/workspaces/{ws['id']}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data['papers'], list)

    # chat endpoint (AI may be disabled — must still return 200 with a response field)
    r = client.post('/chat/', json={'message': 'Summarize', 'workspace_id': ws['id']}, headers=headers)
    assert r.status_code == 200
    assert 'response' in r.json()
