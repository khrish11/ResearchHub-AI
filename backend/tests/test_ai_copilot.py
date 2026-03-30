from __future__ import annotations

import services.copilot_service as copilot_service
from repositories.research import FirebaseResearchRepository, User


def _seed_workspace_with_papers(
    repo: FirebaseResearchRepository,
    user: User,
):
    workspace = repo.create_workspace(user.id, "Copilot WS", "Workspace for copilot tests")
    p1 = repo.create_paper(
        workspace_id=workspace.id,
        title="Adaptive Retrieval for Scientific QA",
        authors="Alice, Bob",
        abstract="Retrieval-focused paper for QA systems.",
        url="https://example.org/p1",
    )
    p2 = repo.create_paper(
        workspace_id=workspace.id,
        title="Contrastive Evaluation of QA Pipelines",
        authors="Carol, Dave",
        abstract="Compares multiple QA pipelines and scoring schemes.",
        url="https://example.org/p2",
    )
    repo.save(p1)
    repo.save(p2)
    return workspace, p1, p2


def test_copilot_intent_classification_examples() -> None:
    cases = [
        ("Explain this paper", {"paper_ids": [1], "workspace_id": 1}, "explain"),
        ("Compare these papers", {"paper_ids": [1, 2], "workspace_id": 1}, "compare"),
        ("Generate a report for this workspace", {"workspace_id": 1}, "report"),
        ("What are the main trends in my workspace?", {"workspace_id": 1}, "insights"),
        ("Summarize my workspace", {"workspace_id": 1}, "rag_query"),
    ]
    for query, context, expected in cases:
        detected = copilot_service.detect_copilot_intent(query=query, context=context)
        assert detected["intent"] == expected
        assert 0.0 <= float(detected["intent_confidence"]) <= 1.0


def test_copilot_routing_explain(
    test_client,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    workspace, paper, _ = _seed_workspace_with_papers(repo, mock_user)

    async def _fake_explain(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "type": "explain",
            "content": {"simple_explanation": "Explained."},
            "sources": [{"source_id": f"paper:{paper.id}", "title": paper.title, "source_type": "paper"}],
            "confidence": 0.88,
        }

    async def _fake_rag(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("RAG fallback should not run for explain route success.")

    monkeypatch.setattr(copilot_service, "_route_explain", _fake_explain)
    monkeypatch.setattr(copilot_service, "_route_rag_query", _fake_rag)

    response = test_client.post(
        "/ai/copilot",
        json={
            "query": "Explain this paper",
            "context": {"workspace_id": workspace.id, "paper_ids": [paper.id]},
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "explain"
    assert payload["fallback_used"] is False
    assert "simple_explanation" in payload["content"]
    assert len(payload["sources"]) >= 1


def test_copilot_routing_compare(
    test_client,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    workspace, p1, p2 = _seed_workspace_with_papers(repo, mock_user)

    async def _fake_compare(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "type": "compare",
            "content": {"comparison": {"summary": "Compared."}},
            "sources": [],
            "confidence": 0.81,
        }

    monkeypatch.setattr(copilot_service, "_route_compare", _fake_compare)

    response = test_client.post(
        "/ai/copilot",
        json={
            "query": "Compare these papers",
            "context": {"workspace_id": workspace.id, "paper_ids": [p1.id, p2.id]},
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "compare"
    assert payload["intent"] == "compare"
    assert payload["fallback_used"] is False


def test_copilot_fallback_behavior(
    test_client,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    workspace, paper, _ = _seed_workspace_with_papers(repo, mock_user)

    async def _explode_explain(**kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("forced explain failure")

    async def _fallback_rag(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "type": "rag_query",
            "content": {"answer": "Fallback answer from RAG route."},
            "sources": [],
            "confidence": 0.44,
        }

    monkeypatch.setattr(copilot_service, "_route_explain", _explode_explain)
    monkeypatch.setattr(copilot_service, "_route_rag_query", _fallback_rag)

    response = test_client.post(
        "/ai/copilot",
        json={
            "query": "Explain this paper",
            "context": {"workspace_id": workspace.id, "paper_ids": [paper.id]},
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "rag_query"
    assert payload["fallback_used"] is True
    assert payload["content"]["answer"] == "Fallback answer from RAG route."
