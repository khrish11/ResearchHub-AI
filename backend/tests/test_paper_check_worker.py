from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta, timezone

from repositories.research import FirebaseResearchRepository, User
from services import paper_check_service
from workers.paper_check_worker import (
    create_message_callback,
    get_worker_metrics_snapshot,
    handle_job_trigger,
    recover_stuck_jobs,
    reset_worker_metrics,
)


def _create_job(
    repo: FirebaseResearchRepository,
    user: User,
    *,
    status: str = "pending",
    raw_text: str = "Introduction\n\nA test paragraph.\n\nConclusion\n\nDone.",
    retry_count: int = 0,
    max_retries: int = 2,
    claimed_by: str | None = None,
    claimed_at: datetime | None = None,
):
    return repo.create_paper_check_job(
        job_id=f"job-{repo._next_id('paper_check_job_test_id')}",
        user_id=int(user.id or 0),
        paper_id=None,
        input_data={"text": raw_text},
        status=status,
        retry_count=retry_count,
        max_retries=max_retries,
        claimed_by=claimed_by,
        claimed_at=claimed_at,
    )


def test_two_workers_cannot_claim_same_job(
    repo: FirebaseResearchRepository,
    mock_user: User,
):
    job = _create_job(repo, mock_user)

    first = repo.claim_next_job("worker-a")
    second = repo.claim_next_job("worker-b")

    assert first is not None
    assert first.job_id == job.job_id
    assert first.claimed_by == "worker-a"
    assert second is None


def test_stuck_job_recovery_resets_retryable_job(
    repo: FirebaseResearchRepository,
    mock_user: User,
):
    job = _create_job(
        repo,
        mock_user,
        status="running",
        retry_count=0,
        max_retries=2,
        claimed_by="dead-worker",
        claimed_at=datetime.now(timezone.utc) - timedelta(seconds=600),
    )

    recovered = asyncio.run(recover_stuck_jobs(repo=repo, job_timeout_seconds=120))
    updated = repo.get_paper_check_job(job.job_id)

    assert recovered == 1
    assert updated is not None
    assert updated.status == "pending"
    assert updated.retry_count == 1
    assert updated.claimed_by is None
    assert updated.claimed_at is None


def test_crash_recovery_resets_and_then_completes_job(
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    monkeypatch.setattr(paper_check_service, "groq_client", None)
    job = _create_job(
        repo,
        mock_user,
        status="running",
        retry_count=0,
        max_retries=2,
        claimed_by="dead-worker",
        claimed_at=datetime.now(timezone.utc) - timedelta(seconds=600),
    )

    recovered = asyncio.run(recover_stuck_jobs(repo=repo, job_timeout_seconds=120))
    assert recovered == 1

    asyncio.run(handle_job_trigger(repo=repo, job_id=job.job_id, worker_id="worker-a"))
    completed = repo.get_paper_check_job(job.job_id)

    assert completed is not None
    assert completed.status == "completed"
    assert completed.retry_count == 1
    assert completed.result is not None


def test_retry_logic_stops_after_max_retries(
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    async def _explode(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(paper_check_service, "run_paper_check", _explode)
    job = _create_job(repo, mock_user, max_retries=1)
    published: list[tuple[str, str]] = []

    def _publish(job_id: str, *, reason: str = "created"):
        published.append((job_id, reason))
        return f"msg-{len(published)}"

    asyncio.run(handle_job_trigger(repo=repo, job_id=job.job_id, worker_id="worker-a", publisher=_publish))
    first = repo.get_paper_check_job(job.job_id)
    assert first is not None
    assert first.status == "pending"
    assert first.retry_count == 1
    assert published and published[-1][0] == job.job_id

    asyncio.run(handle_job_trigger(repo=repo, job_id=job.job_id, worker_id="worker-a", publisher=_publish))
    second = repo.get_paper_check_job(job.job_id)
    assert second is not None
    assert second.status == "failed"
    assert second.retry_count == 2
    assert second.error == "boom"


def test_process_job_is_idempotent_when_completed(
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    job = _create_job(repo, mock_user, status="completed")
    repo.update_job_status(job.job_id, {"result": {"ok": True}})

    async def _explode(**kwargs):
        raise AssertionError("run_paper_check should not execute for completed jobs")

    monkeypatch.setattr(paper_check_service, "run_paper_check", _explode)

    result = asyncio.run(paper_check_service.process_job(repo=repo, job_id=job.job_id))

    assert result is not None
    assert result.status == "completed"
    assert result.result == {"ok": True}


def test_invalid_state_transition_is_rejected(
    repo: FirebaseResearchRepository,
    mock_user: User,
):
    job = _create_job(repo, mock_user, status="pending")

    try:
        repo.update_job_status(job.job_id, {"status": "completed"})
    except ValueError as exc:
        assert "Invalid paper check job transition" in str(exc)
    else:
        raise AssertionError("Expected invalid transition to be rejected.")


def test_job_transitions_pending_to_running_to_completed(
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    monkeypatch.setattr(paper_check_service, "groq_client", None)
    job = _create_job(repo, mock_user)

    completed = asyncio.run(handle_job_trigger(repo=repo, job_id=job.job_id, worker_id="worker-a"))

    assert completed is not None
    assert completed.status == "completed"
    assert completed.result is not None
    assert completed.processing_started_at is not None
    assert completed.processing_completed_at is not None
    assert completed.latency_ms is not None and completed.latency_ms >= 0
    assert completed.attempt_history
    assert completed.attempt_history[-1]["status"] == "completed"
    assert completed.attempt_history[-1]["ended_at"] is not None


def test_duplicate_messages_do_not_duplicate_processing(
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    monkeypatch.setattr(paper_check_service, "groq_client", None)
    job = _create_job(repo, mock_user)
    active_jobs: set[str] = set()

    async def _slow(**kwargs):
        await asyncio.sleep(0.05)
        return {"paper_analysis": {"snapshot": {"summary": "ok"}}, "ai_writing_likelihood": {"segments": []}, "metadata": {}}

    monkeypatch.setattr(paper_check_service, "run_paper_check", _slow)

    async def _run():
        return await asyncio.gather(
            handle_job_trigger(repo=repo, job_id=job.job_id, worker_id="worker-a", active_jobs=active_jobs),
            handle_job_trigger(repo=repo, job_id=job.job_id, worker_id="worker-a", active_jobs=active_jobs),
        )

    first, second = asyncio.run(_run())
    updated = repo.get_paper_check_job(job.job_id)

    assert updated is not None
    assert updated.status == "completed"
    assert len(updated.attempt_history) == 1
    assert first is not None
    assert second is not None


def test_invalid_pubsub_message_is_nacked_for_dead_letter_flow(
    repo: FirebaseResearchRepository,
):
    reset_worker_metrics()

    class _FakeMessage:
        def __init__(self, data: bytes):
            self.data = data
            self.delivery_attempt = 5
            self.acked = False
            self.nacked = False

        def ack(self):
            self.acked = True

        def nack(self):
            self.nacked = True

    callback = create_message_callback(repo=repo, worker_id="worker-a")
    message = _FakeMessage(b"{\"missing\":\"job_id\"}")
    callback(message)
    metrics = get_worker_metrics_snapshot()

    assert message.acked is False
    assert message.nacked is True
    assert metrics["dlq_count"] == 1


def test_valid_pubsub_message_triggers_job_execution(
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    reset_worker_metrics()
    monkeypatch.setattr(paper_check_service, "groq_client", None)
    job = _create_job(repo, mock_user)

    class _FakeMessage:
        def __init__(self, data: bytes):
            self.data = data
            self.delivery_attempt = 1
            self.acked = False
            self.nacked = False

        def ack(self):
            self.acked = True

        def nack(self):
            self.nacked = True

    callback = create_message_callback(repo=repo, worker_id="worker-a")
    message = _FakeMessage(f'{{"job_id":"{job.job_id}"}}'.encode("utf-8"))
    callback(message)
    updated = repo.get_paper_check_job(job.job_id)

    assert message.acked is True
    assert message.nacked is False
    assert updated is not None
    assert updated.status == "completed"


def test_claim_failure_skips_processing_when_job_already_running(
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    reset_worker_metrics()
    job = _create_job(
        repo,
        mock_user,
        status="running",
        claimed_by="other-worker",
        claimed_at=datetime.now(timezone.utc),
    )

    async def _explode(**kwargs):
        raise AssertionError("run_paper_check should not run when claim is unavailable")

    monkeypatch.setattr(paper_check_service, "run_paper_check", _explode)

    result = asyncio.run(handle_job_trigger(repo=repo, job_id=job.job_id, worker_id="worker-a"))
    metrics = get_worker_metrics_snapshot()

    assert result is not None
    assert result.status == "running"
    assert metrics["claim_failures"] >= 1
    assert metrics["jobs_claimed"] == 0


def test_completed_job_is_skipped_without_processing(
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    reset_worker_metrics()
    job = _create_job(repo, mock_user, status="completed")
    repo.update_job_status(job.job_id, {"result": {"ok": True}})

    async def _explode(**kwargs):
        raise AssertionError("run_paper_check should not run for completed jobs")

    monkeypatch.setattr(paper_check_service, "run_paper_check", _explode)

    result = asyncio.run(handle_job_trigger(repo=repo, job_id=job.job_id, worker_id="worker-a"))
    metrics = get_worker_metrics_snapshot()

    assert result is not None
    assert result.status == "completed"
    assert result.result == {"ok": True}
    assert metrics["jobs_skipped"] >= 1
    assert metrics["jobs_claimed"] == 0


def test_backpressure_limit_caps_inflight_processing(
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    reset_worker_metrics()
    monkeypatch.setattr(paper_check_service, "groq_client", None)
    first = _create_job(repo, mock_user, raw_text="Intro\n\nFirst.\n\nEnd.")
    second = _create_job(repo, mock_user, raw_text="Intro\n\nSecond.\n\nEnd.")

    async def _slow(**kwargs):
        await asyncio.sleep(0.05)
        return {
            "paper_analysis": {"snapshot": {"summary": "ok"}},
            "ai_writing_likelihood": {"segments": []},
            "metadata": {},
        }

    monkeypatch.setattr(paper_check_service, "run_paper_check", _slow)

    class _FakeMessage:
        def __init__(self, job_id: str):
            self.data = f'{{"job_id":"{job_id}"}}'.encode("utf-8")
            self.delivery_attempt = 1
            self.acked = False
            self.nacked = False

        def ack(self):
            self.acked = True

        def nack(self):
            self.nacked = True

    callback = create_message_callback(
        repo=repo,
        worker_id="worker-a",
        inflight_semaphore=threading.BoundedSemaphore(1),
    )
    message_one = _FakeMessage(first.job_id)
    message_two = _FakeMessage(second.job_id)

    thread_one = threading.Thread(target=callback, args=(message_one,))
    thread_two = threading.Thread(target=callback, args=(message_two,))
    thread_one.start()
    thread_two.start()
    thread_one.join()
    thread_two.join()

    metrics = get_worker_metrics_snapshot()

    assert message_one.acked is True
    assert message_two.acked is True
    assert metrics["max_inflight_observed"] <= 1
