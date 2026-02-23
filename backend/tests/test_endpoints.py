import os
import sys
from pathlib import Path
# Use a unique temporary file-backed SQLite DB for tests so SQLAlchemy tables
# persist across threads used by TestClient and avoid collisions with running
# servers or other test runs.
import uuid
TEST_DB_PATH = os.path.join(os.path.dirname(__file__), f"test_temp_{uuid.uuid4().hex}.db")
os.environ['DATABASE_URL'] = f'sqlite:///{TEST_DB_PATH}'

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Ensure the temporary test DB file is removed after the test run
import atexit

def _cleanup_test_db():
    try:
        os.remove(TEST_DB_PATH)
    except Exception:
        pass

atexit.register(_cleanup_test_db)

from fastapi.testclient import TestClient
import main

client = TestClient(main.app)

# Ensure the test database schema matches current models (fresh DB for tests).
from database import engine, Base
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)



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


def test_export_workspace():
    token = register_and_get_token('export@example.com')
    headers = {'Authorization': f'Bearer {token}'}

    # create workspace + import a paper
    r = client.post('/workspaces/', json={'name': 'ExportWS'}, headers=headers)
    assert r.status_code == 200
    ws = r.json()

    r = client.post('/papers/import', json={'title': 'ExportPaper', 'authors': ['Auth'], 'abstract': 'Abs', 'doi': '10.1000/example', 'workspace_id': ws['id']}, headers=headers)
    assert r.status_code == 200

    # BibTeX export
    r = client.get(f"/workspaces/{ws['id']}/export?format=bibtex", headers=headers)
    assert r.status_code == 200
    assert '@misc' in r.text or 'ExportPaper' in r.text
    assert '10.1000/example' in r.text

    # CSV export
    r = client.get(f"/workspaces/{ws['id']}/export?format=csv", headers=headers)
    assert r.status_code == 200
    assert 'title,authors' in r.text or 'ExportPaper' in r.text
    assert '10.1000/example' in r.text


def test_search_nasa_requires_token(monkeypatch):
    """Verify behavior when token is missing from process env and/or .env.

    - If `NASA_ADS_TOKEN` is present in `backend/.env` the endpoint should use it
      (fallback behavior).
    - If neither process env nor `.env` contain a token, the endpoint returns 503.
    """
    # Case A: process env missing but backend/.env still has the token -> should work
    monkeypatch.delenv('NASA_ADS_TOKEN', raising=False)
    token = register_and_get_token('nasa-missing@example.com')
    headers = {'Authorization': f'Bearer {token}'}
    r = client.get('/papers/search-nasa', params={'query': 'star', 'max_results': 1}, headers=headers)
    assert r.status_code == 200

    # Case B: simulate BOTH env and .env missing -> return 503
    monkeypatch.setattr('routers.papers.dotenv_values', lambda *a, **k: {})
    monkeypatch.delenv('NASA_ADS_TOKEN', raising=False)
    r2 = client.get('/papers/search-nasa', params={'query': 'star', 'max_results': 1}, headers=headers)
    assert r2.status_code == 503


def test_search_nasa_with_token_and_httpx_mock(monkeypatch):
    """If NASA_ADS_TOKEN is present and ADS responds, `/papers/search-nasa` returns data."""
    # Ensure token available to the server code
    monkeypatch.setenv('NASA_ADS_TOKEN', 'fake-token')

    # Dummy httpx async client that returns a successful response
    class DummyResp:
        status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return {'response': {'docs': [
                {'title': ['T'], 'author': ['A'], 'abstract': 'Abs', 'year': '2020', 'doi': ['10.1'], 'bibcode': '2000X', 'doctype': 'article'}
            ]}}

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def get(self, *args, **kwargs):
            return DummyResp()

    monkeypatch.setattr('routers.papers.httpx.AsyncClient', DummyClient)

    token = register_and_get_token('nasa-ok@example.com')
    headers = {'Authorization': f'Bearer {token}'}
    r = client.get('/papers/search-nasa', params={'query': 'star', 'max_results': 1}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data['papers'] and data['papers'][0]['title'] in ('T', ['T'])


def test_search_plos_with_httpx_mock(monkeypatch):
    class DummyResp:
        status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return {
                "response": {
                    "numFound": 1,
                    "docs": [
                        {
                            "title": "PLOS Paper",
                            "author": ["A. One", "B. Two"],
                            "abstract": ["A test abstract"],
                            "publication_date": "2025-01-01T00:00:00Z",
                            "journal": "PLOS ONE",
                            "doi": "10.1371/journal.pone.0000001",
                        }
                    ],
                }
            }

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def get(self, *args, **kwargs):
            return DummyResp()

    monkeypatch.setattr('routers.papers.httpx.AsyncClient', DummyClient)
    token = register_and_get_token('plos@example.com')
    headers = {'Authorization': f'Bearer {token}'}
    r = client.get('/papers/search-plos', params={'query': 'genomics', 'max_results': 1}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data['papers'] and data['papers'][0]['source'] == 'plos'


def test_search_elife_with_httpx_mock(monkeypatch):
    class DummyResp:
        status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return {
                "hitCount": 1,
                "resultList": {
                    "result": [
                        {
                            "title": "eLife test",
                            "authorList": {"author": [{"fullName": "Jane Doe"}]},
                            "abstractText": "eLife abstract",
                            "firstPublicationDate": "2024-11-20",
                            "doi": "10.7554/eLife.12345",
                        }
                    ]
                },
            }

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def get(self, *args, **kwargs):
            return DummyResp()

    monkeypatch.setattr('routers.papers.httpx.AsyncClient', DummyClient)
    token = register_and_get_token('elife@example.com')
    headers = {'Authorization': f'Bearer {token}'}
    r = client.get('/papers/search-elife', params={'query': 'cell', 'max_results': 1}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data['papers'] and data['papers'][0]['source'] == 'elife'


def test_search_biorxiv_and_medrxiv_with_httpx_mock(monkeypatch):
    class DummyResp:
        status_code = 200
        def __init__(self, server):
            self.server = server
        def raise_for_status(self):
            return None
        def json(self):
            return {
                "collection": [
                    {
                        "title": f"{self.server} paper on transformers",
                        "authors": "A One;B Two",
                        "abstract": "transformers abstract",
                        "date": "2025-01-01",
                        "doi": "10.1101/2025.01.01.123456",
                        "category": "Biology",
                    }
                ]
            }

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def get(self, url, *args, **kwargs):
            server = 'biorxiv' if 'biorxiv' in str(url) else 'medrxiv'
            return DummyResp(server)

    monkeypatch.setattr('routers.papers.httpx.AsyncClient', DummyClient)
    token = register_and_get_token('rxiv@example.com')
    headers = {'Authorization': f'Bearer {token}'}

    rb = client.get('/papers/search-biorxiv', params={'query': 'transformers', 'max_results': 1}, headers=headers)
    rm = client.get('/papers/search-medrxiv', params={'query': 'transformers', 'max_results': 1}, headers=headers)
    assert rb.status_code == 200 and rm.status_code == 200
    assert rb.json()['papers'][0]['source'] == 'biorxiv'
    assert rm.json()['papers'][0]['source'] == 'medrxiv'


def test_global_search_cache_and_metrics(monkeypatch):
    import routers.papers as papers_mod

    def mk_source(label: str):
        async def _fn(*args, **kwargs):
            return {
                "papers": [
                    {
                        "title": f"{label} title",
                        "authors": ["Author"],
                        "abstract": "A",
                        "url": "https://example.org/paper",
                        "published": "2024-01-01",
                        "categories": [label],
                        "source": label,
                    }
                ],
                "notice": None,
            }
        return _fn

    monkeypatch.setattr(papers_mod, 'search_papers', mk_source('arxiv'))
    monkeypatch.setattr(papers_mod, 'search_semantic', mk_source('semantic_scholar'))
    monkeypatch.setattr(papers_mod, 'search_openalex', mk_source('openalex'))
    monkeypatch.setattr(papers_mod, 'search_europepmc', mk_source('europe_pmc'))
    monkeypatch.setattr(papers_mod, 'search_pubmed', mk_source('pubmed'))
    monkeypatch.setattr(papers_mod, 'search_doaj', mk_source('doaj'))
    monkeypatch.setattr(papers_mod, 'search_datacite', mk_source('datacite'))
    monkeypatch.setattr(papers_mod, 'search_hal', mk_source('hal'))
    monkeypatch.setattr(papers_mod, 'search_biorxiv', mk_source('biorxiv'))
    monkeypatch.setattr(papers_mod, 'search_medrxiv', mk_source('medrxiv'))
    monkeypatch.setattr(papers_mod, 'search_plos', mk_source('plos'))
    monkeypatch.setattr(papers_mod, 'search_elife', mk_source('elife'))
    monkeypatch.setattr(papers_mod, 'search_springer', mk_source('springer'))
    monkeypatch.setattr(papers_mod, 'search_nasa_ads', mk_source('nasa_ads'))

    token = register_and_get_token('global-metrics@example.com')
    headers = {'Authorization': f'Bearer {token}'}

    r1 = client.get('/papers/search-global', params={'query': 'gcn', 'max_results': 20}, headers=headers)
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1.get('cache_hit') is False
    assert 'source_status' in d1
    assert 'arxiv' in d1['source_status']

    r2 = client.get('/papers/search-global', params={'query': 'gcn', 'max_results': 20}, headers=headers)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2.get('cache_hit') is True

    m = client.get('/papers/metrics', headers=headers)
    assert m.status_code == 200
    metrics = m.json().get('global_search', {})
    assert int(metrics.get('cache_hits_total', 0)) >= 1


def test_workspace_research_report_exports_pdf_and_docx():
    token = register_and_get_token('report-export@example.com')
    headers = {'Authorization': f'Bearer {token}'}

    ws_resp = client.post('/workspaces/', json={'name': 'ReportWS'}, headers=headers)
    assert ws_resp.status_code == 200
    ws = ws_resp.json()

    imp = client.post(
        '/papers/import',
        json={
            'title': 'Graph Neural Network Paper',
            'authors': ['Alice', 'Bob'],
            'abstract': 'This paper studies graph neural networks for molecular property prediction.',
            'url': 'https://example.org/paper',
            'doi': '10.1000/example',
            'workspace_id': ws['id'],
        },
        headers=headers,
    )
    assert imp.status_code == 200

    pdf_resp = client.post(
        f"/workspaces/{ws['id']}/research-report?format=pdf",
        json={'topic': 'graph neural networks'},
        headers=headers,
    )
    assert pdf_resp.status_code == 200
    assert 'application/pdf' in pdf_resp.headers.get('content-type', '')
    assert pdf_resp.content.startswith(b'%PDF')
    assert len(pdf_resp.content) > 300

    docx_resp = client.post(
        f"/workspaces/{ws['id']}/research-report?format=docx",
        json={'topic': 'graph neural networks'},
        headers=headers,
    )
    assert docx_resp.status_code == 200
    assert 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' in docx_resp.headers.get('content-type', '')
    assert docx_resp.content.startswith(b'PK')
    assert len(docx_resp.content) > 300
