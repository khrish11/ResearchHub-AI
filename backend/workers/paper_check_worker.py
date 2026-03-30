from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from uuid import uuid4


_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from repositories import ResearchRepository
from repositories.research import FirebaseResearchRepository, PaperCheckJob
from services.paper_check_service import HIGH_LATENCY_WARNING_MS, JOB_TIMEOUT_SECONDS, process_job
from utils.paper_check_pubsub import (
    PaperCheckPubSubError,
    ensure_paper_check_pubsub_resources,
    get_paper_check_pubsub_config,
    get_subscriber_client,
    parse_paper_check_message,
    publish_paper_check_job,
)

try:
    from google.api_core.exceptions import Aborted, DeadlineExceeded, InternalServerError, ResourceExhausted, ServiceUnavailable
    from google.cloud import pubsub_v1
except Exception:  # pragma: no cover - optional in local tests
    Aborted = DeadlineExceeded = InternalServerError = ResourceExhausted = ServiceUnavailable = tuple()  # type: ignore[assignment]
    pubsub_v1 = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)

WORKER_ID = str(os.getenv("PAPER_CHECK_WORKER_ID") or uuid4().hex).strip()
JOB_TIMEOUT = max(
    30,
    int(os.getenv("PAPER_CHECK_WORKER_JOB_TIMEOUT", str(JOB_TIMEOUT_SECONDS)) or JOB_TIMEOUT_SECONDS),
)
MAX_CONCURRENT_JOBS = max(
    1,
    int(os.getenv("PAPER_CHECK_WORKER_MAX_CONCURRENT_JOBS", "2") or 2),
)
MAX_INFLIGHT_MESSAGES = max(
    1,
    int(os.getenv("PAPER_CHECK_WORKER_MAX_INFLIGHT_MESSAGES", str(MAX_CONCURRENT_JOBS)) or MAX_CONCURRENT_JOBS),
)
MAX_INFLIGHT_BYTES = max(
    1_048_576,
    int(os.getenv("PAPER_CHECK_WORKER_MAX_INFLIGHT_BYTES", "10485760") or 10485760),
)
RECOVERY_INTERVAL = max(
    10.0,
    float(os.getenv("PAPER_CHECK_WORKER_RECOVERY_INTERVAL_SECONDS", "30") or 30),
)
PENDING_REDISPATCH_SECONDS = max(
    5,
    int(os.getenv("PAPER_CHECK_WORKER_PENDING_REDISPATCH_SECONDS", "30") or 30),
)
MAX_PENDING_REDISPATCH = max(
    1,
    int(os.getenv("PAPER_CHECK_WORKER_MAX_PENDING_REDISPATCH", "50") or 50),
)
FAILURE_RATE_ALERT_THRESHOLD = max(
    0.05,
    min(1.0, float(os.getenv("PAPER_CHECK_WORKER_FAILURE_RATE_ALERT_THRESHOLD", "0.4") or 0.4)),
)
FAILURE_RATE_MIN_SAMPLES = max(
    3,
    int(os.getenv("PAPER_CHECK_WORKER_FAILURE_RATE_MIN_SAMPLES", "5") or 5),
)
_REPO_RETRY_ATTEMPTS = max(2, int(os.getenv("PAPER_CHECK_WORKER_REPO_RETRY_ATTEMPTS", "3") or 3))
_PUBLISH_RETRY_ATTEMPTS = max(2, int(os.getenv("PAPER_CHECK_WORKER_PUBLISH_RETRY_ATTEMPTS", "3") or 3))

_WORKER_METRICS_LOCK = threading.Lock()
_WORKER_METRICS: Dict[str, float] = {
    "messages_received": 0,
    "messages_acked": 0,
    "messages_nacked": 0,
    "jobs_claimed": 0,
    "jobs_completed": 0,
    "jobs_failed": 0,
    "jobs_skipped": 0,
    "claim_failures": 0,
    "dlq_count": 0,
    "inflight_messages": 0,
    "max_inflight_observed": 0,
}


def _is_retryable_exception(exc: Exception) -> bool:
    return not isinstance(exc, ValueError)


def _log_worker_event(event: str, level: int = logging.INFO, **fields: Any) -> None:
    logger.log(level, json.dumps({"event": event, **fields}, default=str))


def reset_worker_metrics() -> None:
    with _WORKER_METRICS_LOCK:
        for key in _WORKER_METRICS:
            _WORKER_METRICS[key] = 0


def _increment_metric(name: str, delta: float = 1) -> None:
    with _WORKER_METRICS_LOCK:
        _WORKER_METRICS[name] = float(_WORKER_METRICS.get(name, 0) + delta)


def _change_inflight(delta: int) -> None:
    with _WORKER_METRICS_LOCK:
        inflight = max(0.0, float(_WORKER_METRICS.get("inflight_messages", 0)) + float(delta))
        _WORKER_METRICS["inflight_messages"] = inflight
        if inflight > float(_WORKER_METRICS.get("max_inflight_observed", 0)):
            _WORKER_METRICS["max_inflight_observed"] = inflight


def get_worker_metrics_snapshot() -> Dict[str, float]:
    with _WORKER_METRICS_LOCK:
        snapshot = {key: float(value) for key, value in _WORKER_METRICS.items()}
    claimed = max(0.0, snapshot.get("jobs_claimed", 0.0))
    failed = max(0.0, snapshot.get("jobs_failed", 0.0))
    snapshot["failure_rate"] = round((failed / claimed), 4) if claimed > 0 else 0.0
    return snapshot


def _maybe_log_failure_rate_alert(reason: str) -> None:
    snapshot = get_worker_metrics_snapshot()
    if snapshot["jobs_claimed"] < FAILURE_RATE_MIN_SAMPLES:
        return
    if snapshot["failure_rate"] < FAILURE_RATE_ALERT_THRESHOLD:
        return
    _log_worker_event(
        "paper_check_failure_rate_alert",
        level=logging.ERROR,
        reason=reason,
        failure_rate=snapshot["failure_rate"],
        jobs_claimed=int(snapshot["jobs_claimed"]),
        jobs_failed=int(snapshot["jobs_failed"]),
        dlq_count=int(snapshot["dlq_count"]),
    )


def _record_dlq_event(
    *,
    job_id: Optional[str],
    worker_id: str,
    reason: str,
    delivery_attempt: Optional[int],
    max_delivery_attempts: int,
) -> None:
    attempt = int(delivery_attempt or 0)
    if attempt < max_delivery_attempts:
        return
    _increment_metric("dlq_count")
    _log_worker_event(
        "paper_check_message_dlq_candidate",
        level=logging.ERROR,
        job_id=job_id,
        worker_id=worker_id,
        reason=reason,
        delivery_attempt=attempt,
        max_delivery_attempts=max_delivery_attempts,
    )


def _is_transient_repo_error(exc: Exception) -> bool:
    transient_types = tuple(
        exc_type
        for exc_type in (Aborted, DeadlineExceeded, InternalServerError, ResourceExhausted, ServiceUnavailable)
        if isinstance(exc_type, type)
    )
    return isinstance(exc, transient_types)


async def _retry_repo_call(
    operation: Callable[..., Any],
    *args: Any,
    retries: int = _REPO_RETRY_ATTEMPTS,
    **kwargs: Any,
) -> Any:
    delay = 0.25
    last_error: Optional[Exception] = None
    for attempt in range(1, max(1, int(retries or 1)) + 1):
        try:
            return operation(*args, **kwargs)
        except Exception as exc:
            last_error = exc
            if not _is_transient_repo_error(exc) or attempt >= retries:
                raise
            await asyncio.sleep(delay)
            delay = min(2.0, delay * 2)
    if last_error is not None:
        raise last_error
    return None


async def _publish_job_trigger(
    job_id: str,
    *,
    reason: str,
    publisher: Callable[[str], Any] | Callable[..., Any] = publish_paper_check_job,
    retries: int = _PUBLISH_RETRY_ATTEMPTS,
) -> Optional[str]:
    delay = 0.25
    last_error: Optional[Exception] = None
    for attempt in range(1, max(1, int(retries or 1)) + 1):
        try:
            message_id = await asyncio.to_thread(publisher, job_id, reason=reason)
            _log_worker_event(
                "paper_check_job_redispatched",
                job_id=job_id,
                reason=reason,
                message_id=message_id,
            )
            return str(message_id)
        except Exception as exc:
            last_error = exc
            if attempt >= retries:
                break
            await asyncio.sleep(delay)
            delay = min(2.0, delay * 2)
    if last_error is not None:
        logger.warning(
            json.dumps(
                {
                    "event": "paper_check_job_redispatch_failed",
                    "job_id": job_id,
                    "reason": reason,
                    "error": str(last_error),
                },
                default=str,
            )
        )
    return None


async def recover_stuck_jobs(
    *,
    repo: ResearchRepository,
    job_timeout_seconds: int = JOB_TIMEOUT,
    publisher: Callable[[str], Any] | Callable[..., Any] = publish_paper_check_job,
) -> int:
    recovered = 0
    stuck_jobs = await _retry_repo_call(repo.get_stuck_jobs, job_timeout_seconds)
    for job in stuck_jobs:
        updated = await _retry_repo_call(
            repo.fail_or_requeue_paper_check_job,
            job.job_id,
            worker_id=None,
            claimed_at=job.claimed_at,
            error_message=f"Paper check worker timed out after {job_timeout_seconds}s.",
            retryable=True,
        )
        if updated and updated.status in {"pending", "failed"}:
            recovered += 1
            _log_worker_event(
                "paper_check_job_recovered",
                job_id=job.job_id,
                worker_id=job.claimed_by,
                retry_count=updated.retry_count,
                status=updated.status,
            )
            if updated.status == "pending":
                await _publish_job_trigger(
                    updated.job_id,
                    reason="stuck_recovery",
                    publisher=publisher,
                )
            if updated.retry_count > 1:
                _log_worker_event(
                    "paper_check_job_retry_warning",
                    level=logging.WARNING,
                    job_id=job.job_id,
                    retry_count=updated.retry_count,
                    max_retries=updated.max_retries,
                )
    return recovered


async def redispatch_pending_jobs(
    *,
    repo: ResearchRepository,
    older_than_seconds: int = PENDING_REDISPATCH_SECONDS,
    limit: int = MAX_PENDING_REDISPATCH,
    publisher: Callable[[str], Any] | Callable[..., Any] = publish_paper_check_job,
) -> int:
    pending_jobs = await _retry_repo_call(
        repo.list_pending_jobs_for_dispatch,
        older_than_seconds=older_than_seconds,
        limit=limit * 2,
    )
    # Priority sorting (high > normal > low)
    pri_order = {"high": 3, "normal": 2, "low": 1}
    pending_jobs.sort(key=lambda j: pri_order.get(str(getattr(j, "priority", "normal")).lower(), 2), reverse=True)
    pending_jobs = pending_jobs[:limit]

    dispatched = 0
    for job in pending_jobs:
        published = await _publish_job_trigger(
            job.job_id,
            reason="pending_recovery",
            publisher=publisher,
        )
        if published:
            dispatched += 1
    return dispatched


async def process_claimed_job(
    *,
    repo: ResearchRepository,
    job: PaperCheckJob,
    worker_id: str,
    job_timeout_seconds: int = JOB_TIMEOUT,
) -> Optional[PaperCheckJob]:
    _log_worker_event(
        "paper_check_job_processing_started",
        job_id=job.job_id,
        worker_id=worker_id,
        retry_count=job.retry_count,
        claimed_at=job.claimed_at,
    )
    try:
        updated = await asyncio.wait_for(
            process_job(
                repo=repo,
                job_id=job.job_id,
                worker_id=worker_id,
                claimed_at=job.claimed_at,
            ),
            timeout=job_timeout_seconds,
        )
        if updated is not None:
            _log_worker_event(
                "paper_check_job_processing_finished",
                job_id=job.job_id,
                worker_id=worker_id,
                status=updated.status,
                retry_count=updated.retry_count,
                latency_ms=updated.latency_ms,
            )
            if updated.status == "completed":
                _increment_metric("jobs_completed")
            elif updated.status == "failed":
                _increment_metric("jobs_failed")
                _maybe_log_failure_rate_alert("terminal_failure")
            if updated.latency_ms is not None and updated.latency_ms > HIGH_LATENCY_WARNING_MS:
                _log_worker_event(
                    "paper_check_job_latency_warning",
                    level=logging.WARNING,
                    job_id=job.job_id,
                    worker_id=worker_id,
                    latency_ms=updated.latency_ms,
                    threshold_ms=HIGH_LATENCY_WARNING_MS,
                )
        return updated
    except asyncio.TimeoutError:
        updated = await _retry_repo_call(
            repo.fail_or_requeue_paper_check_job,
            job.job_id,
            worker_id=worker_id,
            claimed_at=job.claimed_at,
            error_message=f"Paper check timed out after {job_timeout_seconds}s.",
            retryable=True,
        )
        _log_worker_event(
            "paper_check_job_timeout",
            level=logging.WARNING,
            job_id=job.job_id,
            worker_id=worker_id,
            retry_count=updated.retry_count if updated else None,
            status=updated.status if updated else "unknown",
        )
        if updated and updated.status == "failed":
            _increment_metric("jobs_failed")
            _maybe_log_failure_rate_alert("timeout_failure")
        return updated
    except Exception as exc:
        logger.exception("paper_check_job_failed job_id=%s worker_id=%s", job.job_id, worker_id)
        updated = await _retry_repo_call(
            repo.fail_or_requeue_paper_check_job,
            job.job_id,
            worker_id=worker_id,
            claimed_at=job.claimed_at,
            error_message=str(exc) or "Paper check failed.",
            retryable=_is_retryable_exception(exc),
        )
        _log_worker_event(
            "paper_check_job_retry_or_fail",
            level=logging.WARNING,
            job_id=job.job_id,
            worker_id=worker_id,
            status=updated.status if updated else "unknown",
            retry_count=updated.retry_count if updated else None,
            error=str(exc),
        )
        if updated and updated.retry_count > 1:
            _log_worker_event(
                "paper_check_job_retry_warning",
                level=logging.WARNING,
                job_id=job.job_id,
                retry_count=updated.retry_count,
                max_retries=updated.max_retries,
            )
        if updated and updated.status == "failed":
            _increment_metric("jobs_failed")
            _maybe_log_failure_rate_alert("exception_failure")
        return updated


async def handle_job_trigger(
    *,
    repo: ResearchRepository,
    job_id: str,
    worker_id: str = WORKER_ID,
    job_timeout_seconds: int = JOB_TIMEOUT,
    publisher: Callable[[str], Any] | Callable[..., Any] = publish_paper_check_job,
    active_jobs: Optional[set[str]] = None,
    active_jobs_lock: Optional[Any] = None,
) -> Optional[PaperCheckJob]:
    job_token = str(job_id or "").strip()
    if not job_token:
        raise ValueError("job_id is required")

    marked_active = False
    if active_jobs is not None:
        lock = active_jobs_lock or threading.Lock()
        with lock:
            if job_token in active_jobs:
                current = await _retry_repo_call(repo.get_paper_check_job, job_token)
                _increment_metric("jobs_skipped")
                _log_worker_event(
                    "paper_check_job_duplicate_message_ignored",
                    job_id=job_token,
                    worker_id=worker_id,
                    status=current.status if current else "missing",
                )
                return current
            active_jobs.add(job_token)
            marked_active = True

    try:
        current = await _retry_repo_call(repo.get_paper_check_job, job_token)
        if current is None:
            _increment_metric("jobs_skipped")
            _log_worker_event(
                "paper_check_job_trigger_missing",
                level=logging.WARNING,
                job_id=job_token,
                worker_id=worker_id,
            )
            return None
        if current.status not in {"pending", "running"}:
            _increment_metric("jobs_skipped")
            _log_worker_event(
                "paper_check_job_trigger_noop",
                job_id=job_token,
                worker_id=worker_id,
                status=current.status,
            )
            return current
        if current.status == "running":
            _increment_metric("claim_failures")
            _increment_metric("jobs_skipped")
            _log_worker_event(
                "paper_check_job_already_running",
                job_id=job_token,
                worker_id=worker_id,
                claimed_by=current.claimed_by,
            )
            return current

        claimed = await _retry_repo_call(
            repo.claim_paper_check_job,
            job_token,
            worker_id=worker_id,
        )
        if claimed is None:
            _increment_metric("claim_failures")
            return None
        if claimed.status != "running" or claimed.claimed_by != worker_id:
            _increment_metric("claim_failures")
            _increment_metric("jobs_skipped")
            _log_worker_event(
                "paper_check_job_trigger_ignored",
                job_id=job_token,
                worker_id=worker_id,
                status=claimed.status,
                claimed_by=claimed.claimed_by,
            )
            return claimed

        _increment_metric("jobs_claimed")
        updated = await process_claimed_job(
            repo=repo,
            job=claimed,
            worker_id=worker_id,
            job_timeout_seconds=job_timeout_seconds,
        )
        if updated and updated.status == "pending":
            await _publish_job_trigger(
                updated.job_id,
                reason="retry_pending",
                publisher=publisher,
            )
        return updated
    finally:
        if marked_active and active_jobs is not None:
            lock = active_jobs_lock or threading.Lock()
            with lock:
                active_jobs.discard(job_token)


async def run_recovery_iteration(
    *,
    repo: ResearchRepository,
    job_timeout_seconds: int = JOB_TIMEOUT,
    pending_redispatch_seconds: int = PENDING_REDISPATCH_SECONDS,
    pending_limit: int = MAX_PENDING_REDISPATCH,
    publisher: Callable[[str], Any] | Callable[..., Any] = publish_paper_check_job,
) -> Dict[str, int]:
    recovered = await recover_stuck_jobs(
        repo=repo,
        job_timeout_seconds=job_timeout_seconds,
        publisher=publisher,
    )
    redispatched = await redispatch_pending_jobs(
        repo=repo,
        older_than_seconds=pending_redispatch_seconds,
        limit=pending_limit,
        publisher=publisher,
    )
    snapshot = get_worker_metrics_snapshot()
    if recovered or redispatched or snapshot["dlq_count"] or snapshot["jobs_failed"]:
        _log_worker_event(
            "paper_check_worker_metrics",
            worker_id=WORKER_ID,
            recovered=recovered,
            redispatched=redispatched,
            dlq_count=int(snapshot["dlq_count"]),
            failure_rate=snapshot["failure_rate"],
            jobs_claimed=int(snapshot["jobs_claimed"]),
            jobs_failed=int(snapshot["jobs_failed"]),
            inflight_messages=int(snapshot["inflight_messages"]),
            max_inflight_observed=int(snapshot["max_inflight_observed"]),
        )
    return {"recovered": recovered, "redispatched": redispatched}


def create_message_callback(
    *,
    repo: ResearchRepository,
    worker_id: str = WORKER_ID,
    job_timeout_seconds: int = JOB_TIMEOUT,
    publisher: Callable[[str], Any] | Callable[..., Any] = publish_paper_check_job,
    active_jobs: Optional[set[str]] = None,
    active_jobs_lock: Optional[Any] = None,
    inflight_semaphore: Optional[threading.BoundedSemaphore] = None,
    max_delivery_attempts: Optional[int] = None,
):
    tracked_jobs = active_jobs if active_jobs is not None else set()
    tracked_lock = active_jobs_lock if active_jobs_lock is not None else threading.Lock()
    tracked_semaphore = inflight_semaphore if inflight_semaphore is not None else threading.BoundedSemaphore(MAX_INFLIGHT_MESSAGES)
    delivery_limit = max_delivery_attempts or get_paper_check_pubsub_config().max_delivery_attempts

    def _callback(message: Any) -> None:
        delivery_attempt = getattr(message, "delivery_attempt", None)
        _increment_metric("messages_received")
        try:
            attributes = getattr(message, "attributes", None)
            payload = parse_paper_check_message(message.data, attributes)
            job_id = str(payload["job_id"])
            
            partitions_env = os.getenv("PAPER_CHECK_WORKER_PARTITIONS")
            if partitions_env:
                allowed_partitions = {int(p.strip()) for p in partitions_env.split(",") if p.strip().isdigit()}
                qp = payload.get("queue_partition")
                if qp is not None and qp not in allowed_partitions:
                    _increment_metric("jobs_skipped")
                    message.ack()
                    return
                    
            types_env = os.getenv("PAPER_CHECK_WORKER_JOB_TYPES")
            if types_env:
                allowed_types = {t.strip().lower() for t in types_env.split(",") if t.strip()}
                jt = payload.get("job_type", "fast").lower()
                if jt not in allowed_types:
                    _increment_metric("jobs_skipped")
                    message.ack()
                    return
        except Exception as exc:
            _increment_metric("messages_nacked")
            _record_dlq_event(
                job_id=None,
                worker_id=worker_id,
                reason=f"invalid_payload:{exc}",
                delivery_attempt=delivery_attempt,
                max_delivery_attempts=delivery_limit,
            )
            _log_worker_event(
                "paper_check_message_invalid",
                level=logging.ERROR,
                worker_id=worker_id,
                delivery_attempt=delivery_attempt,
                error=str(exc),
            )
            message.nack()
            return

        tracked_semaphore.acquire()
        _change_inflight(1)
        try:
            try:
                asyncio.run(
                    handle_job_trigger(
                        repo=repo,
                        job_id=job_id,
                        worker_id=worker_id,
                        job_timeout_seconds=job_timeout_seconds,
                        publisher=publisher,
                        active_jobs=tracked_jobs,
                        active_jobs_lock=tracked_lock,
                    )
                )
            except Exception as exc:
                logger.exception("paper_check_message_handler_failed job_id=%s worker_id=%s", job_id, worker_id)
                _increment_metric("messages_nacked")
                _record_dlq_event(
                    job_id=job_id,
                    worker_id=worker_id,
                    reason=str(exc),
                    delivery_attempt=delivery_attempt,
                    max_delivery_attempts=delivery_limit,
                )
                _log_worker_event(
                    "paper_check_message_handler_failed",
                    level=logging.ERROR,
                    job_id=job_id,
                    worker_id=worker_id,
                    delivery_attempt=delivery_attempt,
                    error=str(exc),
                )
                message.nack()
                return

            _increment_metric("messages_acked")
            message.ack()
        finally:
            _change_inflight(-1)
            tracked_semaphore.release()

    return _callback


def _run_recovery_loop(
    *,
    repo: ResearchRepository,
    stop_event: threading.Event,
    worker_id: str,
    job_timeout_seconds: int,
    recovery_interval_seconds: float,
    pending_redispatch_seconds: int,
    pending_limit: int,
    publisher: Callable[[str], Any] | Callable[..., Any],
) -> None:
    while not stop_event.is_set():
        try:
            result = asyncio.run(
                run_recovery_iteration(
                    repo=repo,
                    job_timeout_seconds=job_timeout_seconds,
                    pending_redispatch_seconds=pending_redispatch_seconds,
                    pending_limit=pending_limit,
                    publisher=publisher,
                )
            )
            if result["recovered"] or result["redispatched"]:
                _log_worker_event(
                    "paper_check_recovery_iteration",
                    worker_id=worker_id,
                    recovered=result["recovered"],
                    redispatched=result["redispatched"],
                )
        except Exception as exc:
            logger.exception("paper_check_recovery_loop_failed worker_id=%s", worker_id)
            _log_worker_event(
                "paper_check_recovery_loop_failed",
                level=logging.ERROR,
                worker_id=worker_id,
                error=str(exc),
            )
        stop_event.wait(recovery_interval_seconds)


def run_worker(
    *,
    repo: Optional[ResearchRepository] = None,
    worker_id: str = WORKER_ID,
    job_timeout_seconds: int = JOB_TIMEOUT,
    max_concurrent_jobs: int = MAX_CONCURRENT_JOBS,
    recovery_interval_seconds: float = RECOVERY_INTERVAL,
    pending_redispatch_seconds: int = PENDING_REDISPATCH_SECONDS,
    pending_limit: int = MAX_PENDING_REDISPATCH,
) -> None:
    if pubsub_v1 is None:
        raise PaperCheckPubSubError("google-cloud-pubsub is required to run the paper check worker.")

    repository = repo or FirebaseResearchRepository()
    if os.getenv("PAPER_CHECK_PUBSUB_AUTOCREATE", "0").strip() in {"1", "true", "TRUE", "yes"}:
        ensure_paper_check_pubsub_resources()

    config = get_paper_check_pubsub_config()
    subscriber = get_subscriber_client()
    effective_inflight = min(max(1, int(max_concurrent_jobs or 1)), MAX_INFLIGHT_MESSAGES)
    flow_control = pubsub_v1.types.FlowControl(
        max_messages=effective_inflight,
        max_bytes=MAX_INFLIGHT_BYTES,
    )
    active_jobs: set[str] = set()
    active_jobs_lock = threading.Lock()
    inflight_semaphore = threading.BoundedSemaphore(effective_inflight)
    stop_event = threading.Event()
    callback = create_message_callback(
        repo=repository,
        worker_id=worker_id,
        job_timeout_seconds=job_timeout_seconds,
        publisher=publish_paper_check_job,
        active_jobs=active_jobs,
        active_jobs_lock=active_jobs_lock,
        inflight_semaphore=inflight_semaphore,
        max_delivery_attempts=config.max_delivery_attempts,
    )
    recovery_thread = threading.Thread(
        target=_run_recovery_loop,
        kwargs={
            "repo": repository,
            "stop_event": stop_event,
            "worker_id": worker_id,
            "job_timeout_seconds": job_timeout_seconds,
            "recovery_interval_seconds": recovery_interval_seconds,
            "pending_redispatch_seconds": pending_redispatch_seconds,
            "pending_limit": pending_limit,
            "publisher": publish_paper_check_job,
        },
        name="paper-check-recovery",
        daemon=True,
    )
    recovery_thread.start()

    future = subscriber.subscribe(
        config.subscription_path,
        callback=callback,
        flow_control=flow_control,
    )
    _log_worker_event(
        "paper_check_worker_started",
        worker_id=worker_id,
        subscription=config.subscription_path,
        topic=config.topic_path,
        max_concurrent_jobs=effective_inflight,
        max_inflight_bytes=MAX_INFLIGHT_BYTES,
        ack_deadline_seconds=config.ack_deadline_seconds,
        recovery_interval_seconds=recovery_interval_seconds,
    )
    try:
        future.result()
    except KeyboardInterrupt:
        _log_worker_event(
            "paper_check_worker_stopping",
            level=logging.WARNING,
            worker_id=worker_id,
            reason="keyboard_interrupt",
        )
    except concurrent.futures.CancelledError:
        _log_worker_event(
            "paper_check_worker_stopping",
            level=logging.WARNING,
            worker_id=worker_id,
            reason="cancelled",
        )
    finally:
        stop_event.set()
        future.cancel()
        recovery_thread.join(timeout=5)
        close_method = getattr(subscriber, "close", None)
        if callable(close_method):
            close_method()


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    run_worker()


if __name__ == "__main__":
    main()
