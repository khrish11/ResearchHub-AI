from __future__ import annotations

import pytest

from repositories.research import InMemoryResearchRepository
import services.workspace_insights_service as workspace_insights_service


def _seed_workspace(repo: InMemoryResearchRepository) -> tuple[int, int]:
    user = repo.create_user(email="insights@test.local", name="Insights Tester")
    workspace = repo.create_workspace(user_id=int(user.id), name="Auto Insights WS")
    repo.create_paper(
        workspace_id=workspace.id,
        title="Adaptive Retrieval Models",
        authors="A. Author",
        abstract="Paper discusses adaptive retrieval and benchmark trends.",
        url="https://example.org/paper-1",
    )
    repo.create_paper(
        workspace_id=workspace.id,
        title="Robustness Contradictions",
        authors="B. Author",
        abstract="Paper highlights conflicting robustness outcomes under distribution shift.",
        url="https://example.org/paper-2",
    )
    return int(user.id or 0), int(workspace.id or 0)


def test_normalize_workspace_insights_payload_mixed_shapes() -> None:
    raw = {
        "key_themes": [
            {"theme": "Retrieval quality dominates downstream answer quality.", "source_refs": [1, "2", 2, 0]},
            "Benchmark drift appears in newer studies.",
        ],
        "contradictions": {"statement": "One paper reports gains while another reports regressions.", "source_refs": "1,9"},
        "research_gaps": [],
    }
    normalized = workspace_insights_service.normalize_workspace_insights_payload(
        parsed_payload=raw,
        max_source_index=3,
        max_items_per_section=5,
    )
    assert len(normalized["key_themes"]) == 2
    assert normalized["key_themes"][0]["source_refs"] == [1, 2]
    assert len(normalized["contradictions"]) == 1
    assert normalized["contradictions"][0]["source_refs"] == [1]
    assert isinstance(normalized["recommended_next_steps"], list)


@pytest.mark.asyncio
async def test_workspace_insights_generation_and_cache_reuse(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryResearchRepository()
    user_id, workspace_id = _seed_workspace(repo)

    async def _fake_context_rows(**kwargs):  # type: ignore[no-untyped-def]
        return [
            {
                "source_index": 1,
                "vector_id": "vec-1",
                "source_id": "paper_1",
                "source_type": "paper",
                "text": "Adaptive retrieval improves evidence precision.",
                "similarity_score": 0.93,
                "metadata": {"title": "Adaptive Retrieval Models", "url": "https://example.org/paper-1"},
            },
            {
                "source_index": 2,
                "vector_id": "vec-2",
                "source_id": "paper_2",
                "source_type": "paper",
                "text": "Contradictory robustness outcomes are common across datasets.",
                "similarity_score": 0.89,
                "metadata": {"title": "Robustness Contradictions", "url": "https://example.org/paper-2"},
            },
        ]

    def _fake_model(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "key_themes": [{"theme": "Retrieval quality controls answer fidelity.", "source_refs": [1]}],
            "emerging_trends": [{"trend": "Shift toward smaller adaptive rerankers.", "source_refs": [1]}],
            "contradictions": [{"contradiction": "Robustness gains vary by dataset.", "source_refs": [1, 2]}],
            "important_findings": [{"finding": "Precision improves with source filtering.", "source_refs": [1]}],
            "research_gaps": [{"gap": "Limited external-validity reporting.", "source_refs": [2]}],
            "recommended_next_steps": [{"step": "Run controlled cross-dataset replication.", "source_refs": [1, 2]}],
        }

    monkeypatch.setattr(workspace_insights_service, "_build_context_rows", _fake_context_rows)
    monkeypatch.setattr(workspace_insights_service, "_run_workspace_insights_model", _fake_model)

    queued = workspace_insights_service.enqueue_workspace_insights_job(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
        trigger="test_generation",
    )
    assert queued["status"] == "queued"
    job_id = str(queued["job_id"])

    processed = await workspace_insights_service.process_workspace_insights_job(
        repo=repo,
        job_id=job_id,
        worker_id="pytest",
    )
    assert processed is not None
    assert processed.get("status") == "completed"

    latest = workspace_insights_service.get_latest_workspace_insights(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    assert latest is not None
    assert latest.get("payload", {}).get("key_themes")
    assert len(latest.get("sources") or []) >= 1

    cached = workspace_insights_service.enqueue_workspace_insights_job(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
        trigger="test_cached",
    )
    assert cached["status"] in {"cached", "reused"}
    assert cached.get("job_id") is None


@pytest.mark.asyncio
async def test_get_or_generate_workspace_insights_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryResearchRepository()
    user_id, workspace_id = _seed_workspace(repo)

    async def _fake_context_rows(**kwargs):  # type: ignore[no-untyped-def]
        return [
            {
                "source_index": 1,
                "vector_id": "vec-only",
                "source_id": "paper_1",
                "source_type": "paper",
                "text": "Evidence baseline.",
                "similarity_score": 0.84,
                "metadata": {"title": "Adaptive Retrieval Models"},
            }
        ]

    def _fake_model(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "key_themes": [{"theme": "Theme A", "source_refs": [1]}],
            "emerging_trends": [],
            "contradictions": [],
            "important_findings": [{"finding": "Finding A", "source_refs": [1]}],
            "research_gaps": [],
            "recommended_next_steps": [{"step": "Step A", "source_refs": [1]}],
        }

    monkeypatch.setattr(workspace_insights_service, "_build_context_rows", _fake_context_rows)
    monkeypatch.setattr(workspace_insights_service, "_run_workspace_insights_model", _fake_model)

    result = await workspace_insights_service.get_or_generate_workspace_insights(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
        refresh=True,
        run_inline=True,
        trigger="test_inline",
    )
    assert result["status"] in {"completed", "cached", "reused"}
    insight = result.get("insight") or {}
    assert insight.get("payload", {}).get("key_themes")
