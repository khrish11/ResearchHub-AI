from __future__ import annotations

from datetime import datetime, timezone

from repositories.research import FirebaseResearchRepository, User
import services.paper_explain_service as paper_explain_service


def _seed_workspace_and_paper(
    repo: FirebaseResearchRepository,
    user: User,
):
    workspace = repo.create_workspace(
        user.id,
        "Explain WS",
        "Workspace for explain-paper tests",
    )
    paper = repo.create_paper(
        workspace_id=workspace.id,
        title="Unified Retrieval Strategies for Scientific QA",
        authors="Ada Lovelace, Grace Hopper",
        abstract=(
            "This paper proposes a unified retrieval strategy for scientific QA, "
            "combining sparse and dense retrieval with confidence-aware reranking."
        ),
        url="https://example.org/papers/unified-retrieval",
    )
    paper.doi = "10.1000/unified-retrieval"
    paper.source = "openalex"
    repo.save(paper)
    return workspace, paper


def _seed_checker_job(
    repo: FirebaseResearchRepository,
    *,
    user_id: int,
    paper_id: int,
) -> None:
    now = datetime.now(timezone.utc)
    repo.db.collection("paper_check_jobs").document("checker_job_explain").set(
        {
            "job_id": "checker_job_explain",
            "paper_id": int(paper_id),
            "user_id": int(user_id),
            "status": "completed",
            "created_at": now,
            "updated_at": now,
            "result": {
                "paper_analysis": {
                    "snapshot": {
                        "summary": "The work fuses hybrid retrieval with confidence calibration.",
                        "core_problem": "How to improve grounded QA retrieval under noisy corpora.",
                    },
                    "claims": [
                        {
                            "claim": "Hybrid sparse+dense retrieval improves answer grounding.",
                            "support_level": "high",
                            "evidence": "Reported across multiple benchmark suites.",
                        }
                    ],
                    "methods": {
                        "approach": "Two-stage retriever with confidence-aware reranking.",
                        "datasets": ["SciFact", "ArXiv QA"],
                        "metrics": ["F1", "nDCG"],
                    },
                    "evidence_strength": {
                        "score": 0.81,
                        "summary": "Evidence is moderately strong across benchmarks.",
                    },
                    "limitations": ["Limited ablation on domain shift."],
                    "red_flags": [],
                },
                "ai_writing_likelihood": {
                    "segments": [
                        {
                            "segment_id": "seg_1",
                            "likelihood_score": 0.24,
                            "likelihood_band": "low",
                            "reasons": ["citation grounded"],
                        }
                    ]
                },
                "metadata": {"version": "paper-check-v1"},
            },
        }
    )


def test_paper_explain_generation(
    test_client,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    _, paper = _seed_workspace_and_paper(repo, mock_user)
    _seed_checker_job(repo, user_id=int(mock_user.id), paper_id=int(paper.id))

    monkeypatch.setattr(paper_explain_service, "groq_client", object())

    def _fake_structured_task(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "parsed": {
                "simple_explanation": "This paper explains how hybrid retrieval improves grounded scientific QA.",
                "key_points": [
                    "Combines sparse and dense retrieval.",
                    "Adds confidence-aware reranking.",
                ],
                "methodology": "Two-stage hybrid retriever with calibrated reranker.",
                "strengths": ["Grounded benchmark improvements", "Clear retrieval design"],
                "weaknesses": ["Domain-shift coverage is limited"],
                "evidence_quality": "Moderately strong benchmark evidence with known scope limits.",
                "ai_likelihood": "Low advisory AI-writing likelihood signal.",
                "significance": "Improves practical reliability for scientific question answering systems.",
            },
            "error": None,
            "cache_hit": False,
        }

    monkeypatch.setattr(paper_explain_service, "run_structured_json_task", _fake_structured_task)

    response = test_client.get(f"/papers/{paper.id}/explain", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "generated"
    assert data["cached"] is False
    assert "hybrid retrieval" in data["simple_explanation"].lower()
    assert len(data["key_points"]) >= 1
    assert len(data["sources"]) >= 1


def test_paper_explain_cache_reuse(
    test_client,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    _, paper = _seed_workspace_and_paper(repo, mock_user)
    _seed_checker_job(repo, user_id=int(mock_user.id), paper_id=int(paper.id))

    monkeypatch.setattr(paper_explain_service, "groq_client", object())
    call_count = {"count": 0}

    def _fake_structured_task(**kwargs):  # type: ignore[no-untyped-def]
        call_count["count"] += 1
        return {
            "parsed": {
                "simple_explanation": "Cached explain payload",
                "key_points": ["Point A"],
                "methodology": "Method A",
                "strengths": ["Strength A"],
                "weaknesses": ["Weakness A"],
                "evidence_quality": "Evidence A",
                "ai_likelihood": "Low advisory signal",
                "significance": "Significance A",
            },
            "error": None,
            "cache_hit": False,
        }

    monkeypatch.setattr(paper_explain_service, "run_structured_json_task", _fake_structured_task)

    first = test_client.get(f"/papers/{paper.id}/explain", headers=auth_headers)
    assert first.status_code == 200
    assert first.json()["status"] == "generated"

    second = test_client.get(f"/papers/{paper.id}/explain", headers=auth_headers)
    assert second.status_code == 200
    assert second.json()["status"] in {"cached", "reused"}
    assert second.json()["cached"] is True
    assert call_count["count"] == 1


def test_paper_explain_missing_data_fallback(
    test_client,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    _, paper = _seed_workspace_and_paper(repo, mock_user)

    monkeypatch.setattr(paper_explain_service, "groq_client", object())

    def _fake_structured_task(**kwargs):  # type: ignore[no-untyped-def]
        return {"parsed": None, "error": "upstream parsing failed", "cache_hit": False}

    monkeypatch.setattr(paper_explain_service, "run_structured_json_task", _fake_structured_task)

    response = test_client.get(f"/papers/{paper.id}/explain", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "fallback"
    assert isinstance(data["simple_explanation"], str) and data["simple_explanation"]
    assert isinstance(data["key_points"], list) and len(data["key_points"]) >= 1
    assert isinstance(data["ai_likelihood"], str) and data["ai_likelihood"]
