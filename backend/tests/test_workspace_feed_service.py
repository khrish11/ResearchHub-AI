from __future__ import annotations

from datetime import timedelta

import pytest

from repositories.research import InMemoryResearchRepository
import services.workspace_feed_service as workspace_feed_service


def _seed_workspace(repo: InMemoryResearchRepository) -> tuple[int, int]:
    user = repo.create_user(email="feed@test.local", name="Feed Tester")
    workspace = repo.create_workspace(user_id=int(user.id), name="Feed Workspace")
    repo.create_paper(
        workspace_id=workspace.id,
        title="Adaptive Retrieval for QA",
        authors="A. Author",
        abstract="Adaptive retrieval improves answer grounding quality.",
        url="https://example.org/paper-1",
    )
    repo.create_paper(
        workspace_id=workspace.id,
        title="Robustness Contradictions in Evaluation",
        authors="B. Author",
        abstract="Conflicting robustness outcomes appear across datasets.",
        url="https://example.org/paper-2",
    )
    return int(user.id or 0), int(workspace.id or 0)


def _fake_insight_payload() -> dict:
    return {
        "insight_id": "wsi_test",
        "payload": {
            "key_themes": [{"text": "Retrieval quality strongly affects downstream answer trust.", "source_refs": [1]}],
            "emerging_trends": [{"text": "Smaller rerankers are gaining adoption.", "source_refs": [1]}],
            "contradictions": [{"text": "Robustness gains differ by benchmark split.", "source_refs": [1, 2]}],
            "important_findings": [{"text": "Filtering improves factual precision.", "source_refs": [1]}],
            "research_gaps": [{"text": "Few studies report external validity.", "source_refs": [2]}],
            "recommended_next_steps": [{"text": "Compare top two papers directly.", "source_refs": [1, 2]}],
        },
        "sources": [
            {
                "source_index": 1,
                "source_id": "paper:1",
                "source_type": "paper",
                "title": "Adaptive Retrieval for QA",
                "url": "https://example.org/paper-1",
                "doi": "",
                "similarity_score": 0.92,
            },
            {
                "source_index": 2,
                "source_id": "paper:2",
                "source_type": "paper",
                "title": "Robustness Contradictions in Evaluation",
                "url": "https://example.org/paper-2",
                "doi": "",
                "similarity_score": 0.88,
            },
        ],
    }


@pytest.mark.asyncio
async def test_workspace_feed_generation_and_cache_reuse(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryResearchRepository()
    user_id, workspace_id = _seed_workspace(repo)
    fake_insight = _fake_insight_payload()

    async def _fake_generate(**kwargs):  # type: ignore[no-untyped-def]
        return {"status": "completed", "job": {"job_id": "insight_job", "status": "completed"}}

    monkeypatch.setattr(workspace_feed_service, "get_or_generate_workspace_insights", _fake_generate)
    monkeypatch.setattr(workspace_feed_service, "get_latest_workspace_insights", lambda **kwargs: fake_insight)

    queued = workspace_feed_service.enqueue_workspace_feed_job(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
        trigger="test_generation",
    )
    assert queued["status"] == "queued"
    job_id = str(queued["job_id"])

    processed = await workspace_feed_service.process_workspace_feed_job(
        repo=repo,
        job_id=job_id,
        worker_id="pytest",
    )
    assert processed is not None
    assert processed.get("status") == "completed"

    page = workspace_feed_service.get_workspace_feed_page(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
        limit=20,
    )
    assert len(page["items"]) >= 4
    assert page["unread_count"] >= 1

    cached = workspace_feed_service.enqueue_workspace_feed_job(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
        trigger="test_cached",
    )
    assert cached["status"] in {"cached", "reused", "already_pending"}


@pytest.mark.asyncio
async def test_workspace_feed_pagination_and_mark_read(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryResearchRepository()
    user_id, workspace_id = _seed_workspace(repo)
    fake_insight = _fake_insight_payload()

    async def _fake_generate(**kwargs):  # type: ignore[no-untyped-def]
        return {"status": "completed", "job": {"job_id": "insight_job", "status": "completed"}}

    monkeypatch.setattr(workspace_feed_service, "get_or_generate_workspace_insights", _fake_generate)
    monkeypatch.setattr(workspace_feed_service, "get_latest_workspace_insights", lambda **kwargs: fake_insight)

    queued = workspace_feed_service.enqueue_workspace_feed_job(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
        trigger="test_page",
    )
    await workspace_feed_service.process_workspace_feed_job(
        repo=repo,
        job_id=str(queued["job_id"]),
        worker_id="pytest",
    )

    first_page = workspace_feed_service.get_workspace_feed_page(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
        limit=2,
        cursor=None,
    )
    assert len(first_page["items"]) == 2
    assert first_page["next_cursor"] is not None

    first_item = first_page["items"][0]
    updated = workspace_feed_service.mark_workspace_feed_item_read(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
        feed_item_id=str(first_item.get("feed_item_id")),
        read=True,
    )
    assert updated is not None
    assert bool(updated.get("read")) is True

    unread_page = workspace_feed_service.get_workspace_feed_page(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
        include_read=False,
        limit=20,
    )
    assert unread_page["unread_count"] <= first_page["unread_count"]


def test_workspace_feed_periodic_enqueue_for_stale_workspace() -> None:
    repo = InMemoryResearchRepository()
    user_id, workspace_id = _seed_workspace(repo)

    queued_count = workspace_feed_service.enqueue_periodic_workspace_feed_jobs(
        repo=repo,
        max_workspaces=5,
    )
    assert queued_count >= 1

    pending = workspace_feed_service.list_pending_workspace_feed_jobs(repo=repo, limit=20)
    assert any(int(item.get("workspace_id") or 0) == workspace_id for item in pending)
    assert any(int(item.get("user_id") or 0) == user_id for item in pending)


@pytest.mark.asyncio
async def test_workspace_feed_job_retries_then_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryResearchRepository()
    user_id, workspace_id = _seed_workspace(repo)

    async def _explode(**kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("transient feed failure")

    monkeypatch.setattr(workspace_feed_service, "get_or_generate_workspace_insights", _explode)
    monkeypatch.setattr(workspace_feed_service, "get_latest_workspace_insights", lambda **kwargs: None)

    queued = workspace_feed_service.enqueue_workspace_feed_job(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
        trigger="test_retry",
    )
    job_id = str(queued["job_id"])

    first = await workspace_feed_service.process_workspace_feed_job(
        repo=repo,
        job_id=job_id,
        worker_id="pytest",
    )
    assert first is not None
    assert first.get("status") == "pending"
    assert int(first.get("retry_count") or 0) == 1

    second = await workspace_feed_service.process_workspace_feed_job(
        repo=repo,
        job_id=job_id,
        worker_id="pytest",
    )
    assert second is not None
    assert second.get("status") == "failed"
    assert int(second.get("retry_count") or 0) == 2
    assert "transient feed failure" in str(second.get("error") or "")


def test_workspace_feed_stuck_job_recovery() -> None:
    repo = InMemoryResearchRepository()
    user_id, workspace_id = _seed_workspace(repo)

    queued = workspace_feed_service.enqueue_workspace_feed_job(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
        trigger="test_stuck",
    )
    job_id = str(queued["job_id"])
    stale_start = workspace_feed_service._utcnow() - timedelta(
        seconds=workspace_feed_service.JOB_STUCK_TIMEOUT_SECONDS + 5
    )
    workspace_feed_service._persist_job(
        repo=repo,
        payload={
            "job_id": job_id,
            "status": "running",
            "claimed_by": "stale-worker",
            "claimed_at": stale_start,
            "processing_started_at": stale_start,
            "updated_at": stale_start,
        },
        merge=True,
    )

    recovered = workspace_feed_service.recover_stuck_workspace_feed_jobs(
        repo=repo,
        timeout_seconds=workspace_feed_service.JOB_STUCK_TIMEOUT_SECONDS,
        limit=10,
    )
    assert recovered == 1
    row = workspace_feed_service.get_workspace_feed_job(repo=repo, job_id=job_id)
    assert row is not None
    assert row.get("status") == "pending"
    assert int(row.get("retry_count") or 0) >= 1
