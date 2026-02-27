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

    # chat endpoint (AI may be disabled in local/test envs)
    r = client.post('/chat/', json={'message': 'Summarize', 'workspace_id': ws['id']}, headers=headers)
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert 'response' in r.json()
    else:
        assert 'detail' in r.json()


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


def test_workspace_research_report_preview_uses_human_paper_references():
    token = register_and_get_token('report-preview@example.com')
    headers = {'Authorization': f'Bearer {token}'}

    ws_resp = client.post('/workspaces/', json={'name': 'PreviewWS'}, headers=headers)
    assert ws_resp.status_code == 200
    ws = ws_resp.json()

    imp = client.post(
        '/papers/import',
        json={
            'title': 'A Practical GNN Study',
            'authors': ['Alice', 'Bob'],
            'abstract': 'This paper studies practical graph neural network training and evaluation design choices.',
            'url': 'https://example.org/gnn-study',
            'doi': '10.1000/gnn.example',
            'workspace_id': ws['id'],
        },
        headers=headers,
    )
    assert imp.status_code == 200

    preview_resp = client.post(
        f"/workspaces/{ws['id']}/research-report-preview",
        json={'topic': 'graph neural networks', 'depth': 'balanced', 'focus_mode': 'methods'},
        headers=headers,
    )
    assert preview_resp.status_code == 200
    data = preview_resp.json()
    markdown = data.get('markdown', '')
    assert '## Paper Links' in markdown
    assert 'Paper 1' in markdown
    assert '[P1]' not in markdown
    assert isinstance(data.get('mindmap_nodes'), list)
    assert isinstance(data.get('paper_links'), list)


def test_workspace_research_report_preview_builds_fallback_mindmap_nodes(monkeypatch):
    token = register_and_get_token('report-preview-fallback@example.com')
    headers = {'Authorization': f'Bearer {token}'}

    ws_resp = client.post('/workspaces/', json={'name': 'PreviewFallbackWS'}, headers=headers)
    assert ws_resp.status_code == 200
    ws = ws_resp.json()

    imp = client.post(
        '/papers/import',
        json={
            'title': 'Fallback GNN Paper',
            'authors': ['Alice'],
            'abstract': 'This paper reports model comparisons, risks, and practical constraints.',
            'url': 'https://example.org/fallback-gnn',
            'doi': '10.1000/fallback.gnn',
            'workspace_id': ws['id'],
        },
        headers=headers,
    )
    assert imp.status_code == 200

    def _fake_report(*args, **kwargs):
        return (
            "# Research Brief: fallback\n\n"
            "## Executive Summary\nA concise summary.\n\n"
            "## Key Insights\n- Evidence quality varies across datasets.\n- Deployment risk is under-reported.\n"
        )

    monkeypatch.setattr('routers.workspaces._generate_report_markdown', _fake_report)
    preview_resp = client.post(
        f"/workspaces/{ws['id']}/research-report-preview",
        json={'topic': 'fallback map', 'depth': 'balanced', 'focus_mode': 'broad'},
        headers=headers,
    )
    assert preview_resp.status_code == 200
    data = preview_resp.json()
    assert isinstance(data.get('mindmap_nodes'), list)
    assert len(data.get('mindmap_nodes', [])) >= 3


def test_research_capabilities_and_knowledge_graph():
    token = register_and_get_token('research-graph@example.com')
    headers = {'Authorization': f'Bearer {token}'}

    cap = client.get('/research/capabilities', headers=headers)
    assert cap.status_code == 200
    cap_data = cap.json()
    assert 'features' in cap_data
    assert 'autonomous_research_mode' in cap_data['features']

    ws_resp = client.post('/workspaces/', json={'name': 'GraphWS'}, headers=headers)
    assert ws_resp.status_code == 200
    ws = ws_resp.json()

    r1 = client.post(
        '/papers/import',
        json={
            'title': 'Graph Neural Detection for IoT',
            'authors': ['A. One', 'B. Two'],
            'abstract': 'We propose a graph neural network for anomaly detection on UNSW-NB15 with strong accuracy.',
            'url': 'https://example.org/gnn-iot',
            'doi': '10.1000/gnn-iot',
            'workspace_id': ws['id'],
        },
        headers=headers,
    )
    assert r1.status_code == 200

    r2 = client.post(
        '/papers/import',
        json={
            'title': 'Robust Edge Security Classification',
            'authors': ['C. Three'],
            'abstract': 'This study reports precision and recall tradeoffs on NSL-KDD under edge constraints.',
            'url': 'https://example.org/edge-sec',
            'doi': '10.1000/edge-sec',
            'workspace_id': ws['id'],
        },
        headers=headers,
    )
    assert r2.status_code == 200

    graph = client.get('/research/knowledge-graph', params={'workspace_id': ws['id']}, headers=headers)
    assert graph.status_code == 200
    graph_data = graph.json()
    assert isinstance(graph_data.get('nodes'), list)
    assert isinstance(graph_data.get('edges'), list)
    assert graph_data.get('summary', {}).get('papers', 0) >= 2


def test_research_autonomous_mode_with_mocked_global(monkeypatch):
    import routers.research_agent as ra

    async def fake_global(*args, **kwargs):
        return {
            'papers': [
                {
                    'title': 'Secure GNNs for Cyber Defense',
                    'authors': ['Alice', 'Bob'],
                    'abstract': 'We improve anomaly detection accuracy in low-resource IoT environments.',
                    'url': 'https://example.org/secure-gnn',
                    'published': '2024-01-01',
                    'categories': ['security'],
                    'source': 'openalex',
                    'doi': '10.1000/secure-gnn',
                },
                {
                    'title': 'Transformer IDS under Resource Constraints',
                    'authors': ['Carol'],
                    'abstract': 'This paper reports F1 improvements but notes deployment latency challenges.',
                    'url': 'https://example.org/transformer-ids',
                    'published': '2023-03-10',
                    'categories': ['security'],
                    'source': 'arxiv',
                    'doi': '10.1000/transformer-ids',
                },
            ],
            'source_status': {'openalex': {'status': 'ok', 'count': 1}, 'arxiv': {'status': 'ok', 'count': 1}},
        }

    async def fake_citations(candidates, max_lookups=12):
        for idx, cand in enumerate(candidates):
            cand['citation_count'] = 10 - idx

    monkeypatch.setattr(ra, 'search_global', fake_global)
    monkeypatch.setattr(ra, '_enrich_citation_counts', fake_citations)

    token = register_and_get_token('research-auto@example.com')
    headers = {'Authorization': f'Bearer {token}'}

    resp = client.post(
        '/research/autonomous-research',
        json={
            'goal': 'Explore GNNs in cybersecurity after 2021',
            'max_results': 40,
            'import_top_n': 3,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert 'literature_review' in data
    assert 'gap_signals' in data
    assert 'trend_signals' in data
    assert isinstance(data.get('top_papers'), list)


def test_research_agent_remaining_endpoints_smoke(monkeypatch):
    import routers.research_agent as ra

    monkeypatch.setattr(ra, '_llm_generate', lambda *args, **kwargs: 'Deterministic analysis output for tests.')

    async def fake_search_candidates(query, max_results, current_user):
        suffix = abs(hash(str(query))) % 100000
        paper = {
            'index': 1,
            'title': f'{query} suggested paper',
            'abstract': 'Open-source benchmark paper with reproducible evaluation setup.',
            'authors': ['Alex Doe'],
            'source': 'openalex',
            'published': '2024-04-18',
            'year': 2024,
            'doi': f'10.1000/{suffix}',
            'url': f'https://example.org/{suffix}',
            'pdf_url': '',
            'citation_count': 12,
            'relevance_score': 4.2,
            'ranking_score': 6.1,
        }
        return [paper], {'source_status': {'openalex': {'status': 'ok', 'count': 1}}}

    monkeypatch.setattr(ra, '_search_global_candidates', fake_search_candidates)

    token = register_and_get_token('research-smoke@example.com')
    headers = {'Authorization': f'Bearer {token}'}

    ws_resp = client.post('/workspaces/', json={'name': 'ResearchSmokeWS'}, headers=headers)
    assert ws_resp.status_code == 200
    ws = ws_resp.json()

    papers_payload = [
        {
            'title': 'Paper 1: Secure GNN Detection (2024)',
            'authors': ['Alice', 'Bob'],
            'abstract': 'We propose a robust GNN baseline with 92% accuracy on UNSW-NB15 and discuss limitations.',
            'url': 'https://example.org/p1',
            'doi': '10.1000/p1',
            'workspace_id': ws['id'],
        },
        {
            'title': 'Paper 2: Transformer IDS Tradeoffs (2023)',
            'authors': ['Carol'],
            'abstract': 'This paper reports precision and recall tradeoffs with high latency in edge deployment.',
            'url': 'https://example.org/p2',
            'doi': '10.1000/p2',
            'workspace_id': ws['id'],
        },
        {
            'title': 'Paper 3: IoT Security Evaluation Study (2022)',
            'authors': ['Dan'],
            'abstract': 'Benchmark study evaluates generalization risks and failure modes across datasets.',
            'url': 'https://example.org/p3',
            'doi': '10.1000/p3',
            'workspace_id': ws['id'],
        },
    ]

    imported_ids = []
    for payload in papers_payload:
        response = client.post('/papers/import', json=payload, headers=headers)
        assert response.status_code == 200
        imported_ids.append(response.json()['paper_id'])

    gap_resp = client.post(
        '/research/gap-detection',
        json={'workspace_id': ws['id'], 'paper_ids': imported_ids, 'topic': 'GNN cybersecurity'},
        headers=headers,
    )
    assert gap_resp.status_code == 200
    assert 'gaps' in gap_resp.json()

    ma_resp = client.post(
        '/research/multi-agent-analysis',
        json={'workspace_id': ws['id'], 'paper_ids': imported_ids[:2], 'topic': 'GNN cybersecurity'},
        headers=headers,
    )
    assert ma_resp.status_code == 200
    ma_data = ma_resp.json()
    assert 'agents' in ma_data
    assert 'agent_quality' in ma_data
    assert 'overall_quality' in ma_data
    assert ma_data.get('strict_mode') is False

    ma_strict_resp = client.post(
        '/research/multi-agent-analysis',
        json={'workspace_id': ws['id'], 'paper_ids': imported_ids[:2], 'topic': 'GNN cybersecurity', 'strict_mode': True},
        headers=headers,
    )
    assert ma_strict_resp.status_code == 200
    ma_strict_data = ma_strict_resp.json()
    assert ma_strict_data.get('strict_mode') is True
    assert 'orchestrated_plan_quality' in ma_strict_data

    trend_resp = client.post(
        '/research/trend-prediction',
        json={'workspace_id': ws['id']},
        headers=headers,
    )
    assert trend_resp.status_code == 200
    assert 'trend_data' in trend_resp.json()

    exp_resp = client.post(
        '/research/experiment-design',
        json={'workspace_id': ws['id'], 'paper_ids': imported_ids[:2], 'topic': 'Low-resource IoT security'},
        headers=headers,
    )
    assert exp_resp.status_code == 200
    assert 'experiment_design' in exp_resp.json()

    draft_resp = client.post(
        '/research/paper-draft',
        json={
            'workspace_id': ws['id'],
            'paper_ids': imported_ids[:2],
            'topic': 'Benchmarking secure GNN systems',
            'target_format': 'IEEE',
            'citation_style': 'IEEE',
        },
        headers=headers,
    )
    assert draft_resp.status_code == 200
    assert 'draft' in draft_resp.json()

    writing_chat_resp = client.post(
        '/research/chatbot',
        json={
            'workspace_id': ws['id'],
            'paper_ids': imported_ids[:2],
            'topic': 'Benchmarking secure GNN systems',
            'draft_text': 'This draft introduces a secure GNN model but lacks benchmark evidence and structure.',
            'message': 'How should I improve this introduction with stronger evidence?',
            'conversation': [
                {'role': 'user', 'content': 'Can you review my draft structure?'},
                {'role': 'assistant', 'content': 'Add section headings and explicit evidence links.'},
            ],
            'max_actions': 5,
        },
        headers=headers,
    )
    assert writing_chat_resp.status_code == 200
    writing_chat_data = writing_chat_resp.json()
    assert isinstance(writing_chat_data.get('reply'), str)
    assert isinstance(writing_chat_data.get('actions'), list)

    writing_chat_compat_resp = client.post(
        '/research/writing-chat',
        json={
            'workspace_id': ws['id'],
            'paper_ids': imported_ids[:2],
            'message': 'Give a short grounded summary.',
            'conversation': [],
        },
        headers=headers,
    )
    assert writing_chat_compat_resp.status_code == 200

    smart_resp = client.post(
        '/research/smart-read',
        json={'workspace_id': ws['id'], 'paper_id': imported_ids[0]},
        headers=headers,
    )
    assert smart_resp.status_code == 200
    assert 'extraction' in smart_resp.json()

    cmp_resp = client.post(
        '/research/compare-papers',
        json={'workspace_id': ws['id'], 'paper_ids': imported_ids[:2]},
        headers=headers,
    )
    assert cmp_resp.status_code == 200
    assert isinstance(cmp_resp.json().get('table'), list)

    feed_resp = client.post(
        '/research/personalized-feed',
        json={'workspace_id': ws['id'], 'max_suggestions': 8, 'force_live': True, 'refresh_seed': 'test-seed-1'},
        headers=headers,
    )
    assert feed_resp.status_code == 200
    assert 'trending_papers' in feed_resp.json()

    verify_resp = client.post(
        '/research/verify-citations',
        json={
            'workspace_id': ws['id'],
            'paper_ids': imported_ids,
            'draft_text': (
                'Paper 1 reports high anomaly detection performance in constrained IoT settings. '
                'Paper 2 highlights latency and deployment limitations.'
            ),
        },
        headers=headers,
    )
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data.get('claims_analyzed', 0) >= 1
    assert isinstance(verify_data.get('results'), list)


def test_ai_model_selection_endpoint():
    token = register_and_get_token('ai-model-select@example.com')
    headers = {'Authorization': f'Bearer {token}'}

    current = client.get('/ai/models', headers=headers)
    assert current.status_code == 200
    payload = current.json()
    models = payload.get('available_models') or []
    assert isinstance(models, list)
    assert len(models) >= 1

    chosen = models[0]
    update = client.post(
        '/ai/models/select',
        json={'model': chosen, 'apply_to_all': True},
        headers=headers,
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated.get('active_model') == chosen
    assert updated.get('active_longform_model') == chosen


def test_docspace_roundtrip_and_account_overview():
    token = register_and_get_token('docspace-overview@example.com')
    headers = {'Authorization': f'Bearer {token}'}

    ws_resp = client.post('/workspaces/', json={'name': 'Doc Workspace'}, headers=headers)
    assert ws_resp.status_code == 200
    ws = ws_resp.json()

    get_resp = client.get(f"/workspaces/{ws['id']}/docspace", headers=headers)
    assert get_resp.status_code == 200
    doc_payload = get_resp.json()
    assert doc_payload.get('workspace_id') == ws['id']
    assert isinstance(doc_payload.get('content'), str)
    initial_version = int(doc_payload.get('version') or 1)

    update_resp = client.put(
        f"/workspaces/{ws['id']}/docspace",
        json={'title': 'Realtime Notes', 'content': 'Live edit content block.'},
        headers=headers,
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated.get('title') == 'Realtime Notes'
    assert 'Live edit content block.' in (updated.get('content') or '')
    assert int(updated.get('version') or 0) >= initial_version + 1

    overview_resp = client.get('/auth/me/overview', headers=headers)
    assert overview_resp.status_code == 200
    overview = overview_resp.json()
    assert int(overview.get('counts', {}).get('workspaces', 0)) >= 1
    assert int(overview.get('counts', {}).get('documents', 0)) >= 1
