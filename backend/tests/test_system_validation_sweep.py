from __future__ import annotations

import logging
import time
from typing import Any, Dict

import services.paper_explain_service as paper_explain_service
import services.workspace_insights_service as workspace_insights_service
from repositories.research import FirebaseResearchRepository, User
from tests.env_flags import MAX_LATENCY_SECONDS


def _create_workspace(*, test_client, auth_headers: Dict[str, str], name: str = "System QA Workspace") -> int:
    response = test_client.post(
        "/workspaces/",
        json={"name": name, "description": "Workspace created during e2e validation."},
        headers=auth_headers,
    )
    assert response.status_code in (200, 201), response.text
    payload = response.json()
    workspace_id = int(payload.get("id") or 0)
    assert workspace_id > 0
    return workspace_id


def _import_paper(
    *,
    test_client,
    auth_headers: Dict[str, str],
    workspace_id: int,
    title: str,
    doi: str,
    abstract: str,
    authors: list[str] | None = None,
) -> int:
    response = test_client.post(
        "/papers/import",
        json={
            "workspace_id": int(workspace_id),
            "title": title,
            "authors": authors if authors is not None else ["Test Author"],
            "abstract": abstract,
            "doi": doi,
            "url": "https://example.org/paper",
            "source": "qa_import",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    paper_id = int(payload.get("paper_id") or 0)
    assert paper_id > 0
    return paper_id


def _patch_workspace_insights_generation(monkeypatch, *, source_title: str = "Context Source") -> None:
    async def _fake_context_rows(**kwargs):  # type: ignore[no-untyped-def]
        return [
            {
                "source_index": 1,
                "vector_id": "vec_1",
                "source_id": "paper:1",
                "source_type": "paper",
                "text": "Hybrid retrieval improved grounded QA and reduced unsupported claims.",
                "similarity_score": 0.93,
                "metadata": {
                    "title": source_title,
                    "url": "https://example.org/context",
                    "doi": "10.1000/context",
                },
            }
        ]

    def _fake_model(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "key_themes": [{"theme": "Grounded retrieval improves answer quality", "source_refs": [1]}],
            "emerging_trends": [{"trend": "RAG-style evaluation is increasing", "source_refs": [1]}],
            "contradictions": [{"contradiction": "Some studies trade latency for faithfulness", "source_refs": [1]}],
            "important_findings": [{"finding": "Faithfulness gains were consistent", "source_refs": [1]}],
            "research_gaps": [{"gap": "Long-context evaluation remains limited", "source_refs": [1]}],
            "recommended_next_steps": [{"step": "Run an ablation across retrieval depth", "source_refs": [1]}],
        }

    monkeypatch.setattr(workspace_insights_service, "_build_context_rows", _fake_context_rows)
    monkeypatch.setattr(workspace_insights_service, "_run_workspace_insights_model", _fake_model)


def test_critical_user_flows_end_to_end(
    test_client,
    auth_headers: Dict[str, str],
    monkeypatch,
    caplog,
):
    caplog.set_level(logging.ERROR)

    workspace_id = _create_workspace(test_client=test_client, auth_headers=auth_headers)

    onboarding = test_client.get(
        f"/onboarding/status?workspace_id={workspace_id}",
        headers=auth_headers,
    )
    assert onboarding.status_code == 200
    onboarding_payload = onboarding.json()
    assert onboarding_payload.get("workspace_id") == workspace_id
    assert isinstance(onboarding_payload.get("needs_onboarding"), bool)

    demo_start = test_client.post(
        "/demo/start",
        json={"workspace_id": workspace_id},
        headers=auth_headers,
    )
    assert demo_start.status_code == 200
    demo_payload = demo_start.json()
    assert demo_payload.get("is_demo_mode") is True

    paper_a = _import_paper(
        test_client=test_client,
        auth_headers=auth_headers,
        workspace_id=workspace_id,
        title="Retrieval-Augmented Scientific QA",
        doi="10.1000/qa-a",
        abstract="This paper studies grounded retrieval for scientific question answering.",
    )
    paper_b = _import_paper(
        test_client=test_client,
        auth_headers=auth_headers,
        workspace_id=workspace_id,
        title="Comparative Study of QA Pipelines",
        doi="10.1000/qa-b",
        abstract="This paper compares QA pipelines with emphasis on evidence fidelity.",
    )

    monkeypatch.setattr(paper_explain_service, "groq_client", object())

    def _fake_structured_explain(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "parsed": {
                "simple_explanation": "This paper explains how grounded retrieval improves research QA.",
                "key_points": ["Retrieval improved factual grounding", "Evidence linking reduced unsupported claims"],
                "methodology": "The authors compare retrieval settings across benchmarks.",
                "strengths": ["Clear evaluation setup", "Grounding-focused metrics"],
                "weaknesses": ["Limited domain diversity"],
                "evidence_quality": "Moderate-to-strong based on benchmark evidence.",
                "ai_likelihood": "Low advisory AI-writing likelihood from checker signal.",
                "significance": "It improves trust in research copilots.",
            },
            "error": None,
        }

    monkeypatch.setattr(paper_explain_service, "run_structured_json_task", _fake_structured_explain)

    explain = test_client.get(f"/papers/{paper_a}/explain", headers=auth_headers)
    assert explain.status_code == 200
    explain_payload = explain.json()
    assert explain_payload.get("paper_id") == paper_a
    assert explain_payload.get("simple_explanation")

    def _fake_compare(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "comparison": {
                "summary": "Paper A emphasizes grounding; Paper B emphasizes evaluation breadth.",
                "recommendation": "Combine both approaches for best coverage and reliability.",
            }
        }

    monkeypatch.setattr("routers.papers.aggregate_and_compare_papers", _fake_compare)

    compare = test_client.post(
        "/papers/compare",
        json={"paper_ids": [paper_a, paper_b], "optional_context": "Focus on reliability and evidence quality."},
        headers=auth_headers,
    )
    assert compare.status_code == 200
    compare_payload = compare.json()
    assert compare_payload.get("status") == "success"

    report_preview = test_client.post(
        f"/workspaces/{workspace_id}/research-report-preview",
        json={"topic": "Grounded research copilots", "depth": "balanced", "focus_mode": "broad"},
        headers=auth_headers,
    )
    assert report_preview.status_code == 200
    report_payload = report_preview.json()
    assert isinstance(report_payload.get("markdown"), str)
    assert len(report_payload.get("markdown") or "") > 20

    async def _fake_copilot(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "type": "rag_query",
            "intent": "rag_query",
            "content": {"answer": "Main trend: stronger grounding and evidence tracking."},
            "sources": [{"source_id": f"paper:{paper_a}", "source_type": "paper", "title": "Retrieval-Augmented Scientific QA"}],
            "confidence": 0.84,
            "fallback_used": False,
            "cached": False,
            "cache_layer": None,
            "intent_scores": {"rag_query": 0.9},
            "context": {"workspace_id": workspace_id, "paper_ids": [paper_a, paper_b]},
        }

    monkeypatch.setattr("routers.ai.run_unified_copilot", _fake_copilot)

    copilot = test_client.post(
        "/ai/copilot",
        json={
            "query": "What are the main trends?",
            "context": {"workspace_id": workspace_id, "paper_ids": [paper_a, paper_b]},
        },
        headers=auth_headers,
    )
    assert copilot.status_code == 200
    copilot_payload = copilot.json()
    assert copilot_payload.get("type") == "rag_query"
    assert copilot_payload.get("content", {}).get("answer")

    _patch_workspace_insights_generation(monkeypatch, source_title="Retrieval-Augmented Scientific QA")

    insights = test_client.get(f"/workspace-insights/{workspace_id}", headers=auth_headers)
    assert insights.status_code == 200
    insights_payload = insights.json()
    assert isinstance(insights_payload.get("payload", {}).get("key_themes"), list)
    assert len(insights_payload.get("payload", {}).get("key_themes") or []) >= 1

    feed = test_client.get(f"/workspace-feed/{workspace_id}", headers=auth_headers)
    assert feed.status_code == 200
    feed_payload = feed.json()
    assert isinstance(feed_payload.get("items"), list)
    assert len(feed_payload.get("items") or []) >= 1

    feed_item_id = str(feed_payload["items"][0]["feed_item_id"])
    mark_read = test_client.post(
        f"/workspace-feed/{workspace_id}/items/{feed_item_id}/read",
        json={"read": True},
        headers=auth_headers,
    )
    assert mark_read.status_code == 200
    mark_payload = mark_read.json()
    assert mark_payload.get("read") is True

    error_records = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert not error_records


def test_edge_cases_empty_large_missing_metadata_and_duplicates(
    test_client,
    auth_headers: Dict[str, str],
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    workspace_id = _create_workspace(test_client=test_client, auth_headers=auth_headers, name="Edge Cases Workspace")

    async def _empty_context_rows(**kwargs):  # type: ignore[no-untyped-def]
        return []

    def _empty_model(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "key_themes": [],
            "emerging_trends": [],
            "contradictions": [],
            "important_findings": [],
            "research_gaps": [],
            "recommended_next_steps": [],
        }

    monkeypatch.setattr(workspace_insights_service, "_build_context_rows", _empty_context_rows)
    monkeypatch.setattr(workspace_insights_service, "_run_workspace_insights_model", _empty_model)

    empty_insights = test_client.get(f"/workspace-insights/{workspace_id}", headers=auth_headers)
    assert empty_insights.status_code == 200
    empty_payload = empty_insights.json()
    assert empty_payload.get("workspace_id") == workspace_id
    assert empty_payload.get("payload", {}).get("key_themes") == []

    empty_feed = test_client.get(f"/workspace-feed/{workspace_id}", headers=auth_headers)
    assert empty_feed.status_code == 200
    assert isinstance(empty_feed.json().get("items"), list)

    missing_meta_import = test_client.post(
        "/papers/import",
        json={
            "workspace_id": workspace_id,
            "title": "Minimal Metadata Paper",
            "authors": [],
            "abstract": "",
            "doi": None,
            "url": None,
            "source": "qa_import",
        },
        headers=auth_headers,
    )
    assert missing_meta_import.status_code == 200

    duplicate_a = test_client.post(
        "/papers/import",
        json={
            "workspace_id": workspace_id,
            "title": "Duplicate DOI Paper",
            "authors": ["Edge Author"],
            "abstract": "First import.",
            "doi": "10.4242/duplicate",
            "url": "https://example.org/duplicate",
            "source": "qa_import",
        },
        headers=auth_headers,
    )
    duplicate_b = test_client.post(
        "/papers/import",
        json={
            "workspace_id": workspace_id,
            "title": "Duplicate DOI Paper",
            "authors": ["Edge Author"],
            "abstract": "Second import should update existing record.",
            "doi": "10.4242/duplicate",
            "url": "https://example.org/duplicate",
            "source": "qa_import",
        },
        headers=auth_headers,
    )
    assert duplicate_a.status_code == 200
    assert duplicate_b.status_code == 200
    assert duplicate_a.json().get("updated") is False
    assert duplicate_b.json().get("updated") is True

    for index in range(120):
        paper = repo.create_paper(
            workspace_id=workspace_id,
            title=f"Large Workspace Paper {index}",
            authors="Scale Tester",
            abstract="Synthetic abstract for scale validation.",
            url=f"https://example.org/large/{index}",
        )
        repo.save(paper)

    large_workspace_detail = test_client.get(f"/workspaces/{workspace_id}", headers=auth_headers)
    assert large_workspace_detail.status_code == 200
    paper_count = len(large_workspace_detail.json().get("papers") or [])
    assert paper_count >= 120

    refreshed_insights = test_client.get(
        f"/workspace-insights/{workspace_id}?refresh=true",
        headers=auth_headers,
    )
    assert refreshed_insights.status_code == 200

    refreshed_feed = test_client.get(
        f"/workspace-feed/{workspace_id}?refresh=true",
        headers=auth_headers,
    )
    assert refreshed_feed.status_code == 200


def test_network_failure_simulation_and_graceful_handling(
    test_client,
    auth_headers: Dict[str, str],
    monkeypatch,
):
    workspace_id = _create_workspace(test_client=test_client, auth_headers=auth_headers, name="Failure Simulation Workspace")
    paper_id = _import_paper(
        test_client=test_client,
        auth_headers=auth_headers,
        workspace_id=workspace_id,
        title="Failure Simulation Paper",
        doi="10.9999/failure",
        abstract="Paper used for failure-path testing.",
    )

    async def _copilot_timeout(**kwargs):  # type: ignore[no-untyped-def]
        raise TimeoutError("upstream timeout")

    monkeypatch.setattr("routers.ai.run_unified_copilot", _copilot_timeout)

    copilot_timeout = test_client.post(
        "/ai/copilot",
        json={"query": "Summarize my workspace", "context": {"workspace_id": workspace_id}},
        headers=auth_headers,
    )
    assert copilot_timeout.status_code == 500
    timeout_payload = copilot_timeout.json()
    assert timeout_payload.get("error_code") == "INTERNAL_ERROR"
    assert "Copilot failed" in str(timeout_payload.get("message") or "")

    monkeypatch.setattr(paper_explain_service, "groq_client", object())

    def _partial_explain(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "parsed": {
                "simple_explanation": "Partial payload from upstream.",
                "methodology": "Method details were partially available.",
            },
            "error": "partial_response",
        }

    monkeypatch.setattr(paper_explain_service, "run_structured_json_task", _partial_explain)
    partial = test_client.get(f"/papers/{paper_id}/explain?refresh=true", headers=auth_headers)
    assert partial.status_code == 200
    partial_payload = partial.json()
    assert partial_payload.get("simple_explanation")
    assert isinstance(partial_payload.get("key_points"), list)

    def _failed_explain(**kwargs):  # type: ignore[no-untyped-def]
        return {"parsed": None, "error": "simulated_llm_timeout"}

    monkeypatch.setattr(paper_explain_service, "run_structured_json_task", _failed_explain)
    failed = test_client.get(f"/papers/{paper_id}/explain?refresh=true", headers=auth_headers)
    assert failed.status_code == 200
    failed_payload = failed.json()
    assert failed_payload.get("status") == "fallback"
    assert "simulated_llm_timeout" in str(failed_payload.get("error") or "")

    async def _context_rows(**kwargs):  # type: ignore[no-untyped-def]
        return [
            {
                "source_index": 1,
                "vector_id": "vec_fail",
                "source_id": "paper:1",
                "source_type": "paper",
                "text": "Minimal context row.",
                "similarity_score": 0.7,
                "metadata": {"title": "Failure Source"},
            }
        ]

    def _insight_failure(**kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated insights model failure")

    monkeypatch.setattr(workspace_insights_service, "_build_context_rows", _context_rows)
    monkeypatch.setattr(workspace_insights_service, "_run_workspace_insights_model", _insight_failure)

    insights_failure = test_client.get(
        f"/workspace-insights/{workspace_id}?refresh=true",
        headers=auth_headers,
    )
    assert insights_failure.status_code == 200
    insights_failure_payload = insights_failure.json()
    status = str(insights_failure_payload.get("status") or "")
    assert status in {"failed", "pending", "queued"}
    if status == "failed":
        assert insights_failure_payload.get("error")


def test_performance_smoke_and_repeated_request_behavior(
    test_client,
    auth_headers: Dict[str, str],
    monkeypatch,
):
    workspace_id = _create_workspace(test_client=test_client, auth_headers=auth_headers, name="Performance Workspace")
    paper_a = _import_paper(
        test_client=test_client,
        auth_headers=auth_headers,
        workspace_id=workspace_id,
        title="Performance Paper A",
        doi="10.1111/perf-a",
        abstract="Performance-focused paper A.",
    )
    paper_b = _import_paper(
        test_client=test_client,
        auth_headers=auth_headers,
        workspace_id=workspace_id,
        title="Performance Paper B",
        doi="10.1111/perf-b",
        abstract="Performance-focused paper B.",
    )

    monkeypatch.setattr(paper_explain_service, "groq_client", object())

    def _fast_explain(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "parsed": {
                "simple_explanation": "Fast explain response.",
                "key_points": ["Point 1"],
                "methodology": "Fast method summary.",
                "strengths": ["Fast strength"],
                "weaknesses": ["Fast weakness"],
                "evidence_quality": "Moderate.",
                "ai_likelihood": "Low.",
                "significance": "Useful for speed test.",
            },
            "error": None,
        }

    monkeypatch.setattr(paper_explain_service, "run_structured_json_task", _fast_explain)

    def _fast_compare(**kwargs):  # type: ignore[no-untyped-def]
        return {"comparison": {"summary": "Fast comparison."}}

    monkeypatch.setattr("routers.papers.aggregate_and_compare_papers", _fast_compare)

    async def _fast_copilot(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "type": "rag_query",
            "intent": "rag_query",
            "content": {"answer": "Fast copilot response."},
            "sources": [],
            "confidence": 0.75,
            "fallback_used": False,
            "cached": False,
            "cache_layer": None,
            "intent_scores": {"rag_query": 0.8},
            "context": {"workspace_id": workspace_id},
        }

    monkeypatch.setattr("routers.ai.run_unified_copilot", _fast_copilot)

    call_counter = {"insights_model_calls": 0}

    async def _fast_context_rows(**kwargs):  # type: ignore[no-untyped-def]
        return [
            {
                "source_index": 1,
                "vector_id": "vec_perf",
                "source_id": "paper:1",
                "source_type": "paper",
                "text": "Fast context for performance checks.",
                "similarity_score": 0.88,
                "metadata": {"title": "Performance Context"},
            }
        ]

    def _fast_model(**kwargs):  # type: ignore[no-untyped-def]
        call_counter["insights_model_calls"] += 1
        return {
            "key_themes": [{"theme": "Fast theme", "source_refs": [1]}],
            "emerging_trends": [],
            "contradictions": [],
            "important_findings": [],
            "research_gaps": [],
            "recommended_next_steps": [],
        }

    monkeypatch.setattr(workspace_insights_service, "_build_context_rows", _fast_context_rows)
    monkeypatch.setattr(workspace_insights_service, "_run_workspace_insights_model", _fast_model)

    timings: Dict[str, float] = {}

    def _timed(name: str, fn):  # type: ignore[no-untyped-def]
        start = time.perf_counter()
        response = fn()
        timings[name] = time.perf_counter() - start
        return response

    onboarding = _timed(
        "onboarding_status",
        lambda: test_client.get(f"/onboarding/status?workspace_id={workspace_id}", headers=auth_headers),
    )
    assert onboarding.status_code == 200

    explain = _timed(
        "explain",
        lambda: test_client.get(f"/papers/{paper_a}/explain", headers=auth_headers),
    )
    assert explain.status_code == 200

    compare = _timed(
        "compare",
        lambda: test_client.post(
            "/papers/compare",
            json={"paper_ids": [paper_a, paper_b]},
            headers=auth_headers,
        ),
    )
    assert compare.status_code == 200

    report = _timed(
        "report_preview",
        lambda: test_client.post(
            f"/workspaces/{workspace_id}/research-report-preview",
            json={"topic": "Perf", "depth": "quick", "focus_mode": "broad"},
            headers=auth_headers,
        ),
    )
    assert report.status_code == 200

    copilot = _timed(
        "copilot",
        lambda: test_client.post(
            "/ai/copilot",
            json={"query": "Summarize my workspace", "context": {"workspace_id": workspace_id}},
            headers=auth_headers,
        ),
    )
    assert copilot.status_code == 200

    insights_first = _timed(
        "insights_first",
        lambda: test_client.get(f"/workspace-insights/{workspace_id}", headers=auth_headers),
    )
    assert insights_first.status_code == 200

    insights_second = _timed(
        "insights_second",
        lambda: test_client.get(f"/workspace-insights/{workspace_id}", headers=auth_headers),
    )
    assert insights_second.status_code == 200

    feed_first = _timed(
        "feed_first",
        lambda: test_client.get(f"/workspace-feed/{workspace_id}", headers=auth_headers),
    )
    assert feed_first.status_code == 200
    feed_second = _timed(
        "feed_second",
        lambda: test_client.get(f"/workspace-feed/{workspace_id}", headers=auth_headers),
    )
    assert feed_second.status_code == 200

    feed_a = feed_first.json()
    feed_b = feed_second.json()
    assert int(feed_b.get("total_count") or 0) == int(feed_a.get("total_count") or 0)

    assert call_counter["insights_model_calls"] <= 1

    slow = {
        name: seconds for name, seconds in timings.items()
        if seconds > MAX_LATENCY_SECONDS
    }
    assert not slow, f"Endpoints slower than {MAX_LATENCY_SECONDS}s: {slow}"
