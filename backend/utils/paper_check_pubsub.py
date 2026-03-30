from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Optional

try:
    from google.api_core.exceptions import (
        Aborted,
        AlreadyExists,
        DeadlineExceeded,
        InternalServerError,
        ResourceExhausted,
        ServiceUnavailable,
    )
    from google.cloud import pubsub_v1
except Exception:  # pragma: no cover - optional in local tests
    Aborted = DeadlineExceeded = InternalServerError = ResourceExhausted = ServiceUnavailable = None  # type: ignore[assignment]
    AlreadyExists = None  # type: ignore[assignment]
    pubsub_v1 = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)
_PUBLISH_TIMEOUT_SECONDS = max(
    5.0,
    float(os.getenv("PAPER_CHECK_PUBSUB_PUBLISH_TIMEOUT_SECONDS", "15") or 15),
)
_PUBLISH_MAX_ATTEMPTS = max(
    1,
    int(os.getenv("PAPER_CHECK_PUBSUB_PUBLISH_MAX_ATTEMPTS", "3") or 3),
)
_PUBLISH_RETRY_BASE_DELAY_SECONDS = max(
    0.05,
    float(os.getenv("PAPER_CHECK_PUBSUB_PUBLISH_RETRY_BASE_DELAY_SECONDS", "0.25") or 0.25),
)
_PUBLISH_RETRY_MAX_DELAY_SECONDS = max(
    _PUBLISH_RETRY_BASE_DELAY_SECONDS,
    float(os.getenv("PAPER_CHECK_PUBSUB_PUBLISH_RETRY_MAX_DELAY_SECONDS", "2.0") or 2.0),
)


class PaperCheckPubSubError(RuntimeError):
    pass


@dataclass(frozen=True)
class PaperCheckPubSubConfig:
    project_id: str
    topic_id: str
    subscription_id: str
    dead_letter_topic_id: str
    max_delivery_attempts: int
    ack_deadline_seconds: int

    @property
    def topic_path(self) -> str:
        return f"projects/{self.project_id}/topics/{self.topic_id}"

    @property
    def subscription_path(self) -> str:
        return f"projects/{self.project_id}/subscriptions/{self.subscription_id}"

    @property
    def dead_letter_topic_path(self) -> str:
        return f"projects/{self.project_id}/topics/{self.dead_letter_topic_id}"


def _env_str(name: str, default: str) -> str:
    value = str(os.getenv(name, default) or default).strip()
    return value or default


def _env_int(name: str, default: int, minimum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


@lru_cache(maxsize=1)
def get_paper_check_pubsub_config() -> PaperCheckPubSubConfig:
    project_id = _env_str(
        "GOOGLE_CLOUD_PROJECT",
        _env_str("FIREBASE_PROJECT_ID", ""),
    )
    if not project_id:
        raise PaperCheckPubSubError("GOOGLE_CLOUD_PROJECT or FIREBASE_PROJECT_ID is required for Pub/Sub.")
    return PaperCheckPubSubConfig(
        project_id=project_id,
        topic_id=_env_str("PAPER_CHECK_PUBSUB_TOPIC", "paper-check-jobs"),
        subscription_id=_env_str("PAPER_CHECK_PUBSUB_SUBSCRIPTION", "paper-check-jobs-sub"),
        dead_letter_topic_id=_env_str("PAPER_CHECK_PUBSUB_DEAD_LETTER_TOPIC", "paper-check-jobs-dlq"),
        max_delivery_attempts=_env_int("PAPER_CHECK_PUBSUB_MAX_DELIVERY_ATTEMPTS", 5, 5),
        ack_deadline_seconds=_env_int("PAPER_CHECK_PUBSUB_ACK_DEADLINE_SECONDS", 120, 10),
    )


@lru_cache(maxsize=1)
def get_publisher_client():
    if pubsub_v1 is None:
        raise PaperCheckPubSubError("google-cloud-pubsub is not installed.")
    return pubsub_v1.PublisherClient()


@lru_cache(maxsize=1)
def get_subscriber_client():
    if pubsub_v1 is None:
        raise PaperCheckPubSubError("google-cloud-pubsub is not installed.")
    return pubsub_v1.SubscriberClient()


def build_subscription_request(
    *,
    config: Optional[PaperCheckPubSubConfig] = None,
) -> Dict[str, Any]:
    cfg = config or get_paper_check_pubsub_config()
    if pubsub_v1 is None:
        raise PaperCheckPubSubError("google-cloud-pubsub is not installed.")
    return {
        "name": cfg.subscription_path,
        "topic": cfg.topic_path,
        "ack_deadline_seconds": cfg.ack_deadline_seconds,
        "dead_letter_policy": pubsub_v1.types.DeadLetterPolicy(
            dead_letter_topic=cfg.dead_letter_topic_path,
            max_delivery_attempts=cfg.max_delivery_attempts,
        ),
    }


def ensure_paper_check_pubsub_resources(
    *,
    config: Optional[PaperCheckPubSubConfig] = None,
) -> Dict[str, str]:
    cfg = config or get_paper_check_pubsub_config()
    publisher = get_publisher_client()
    subscriber = get_subscriber_client()

    for topic_path in (cfg.topic_path, cfg.dead_letter_topic_path):
        try:
            publisher.create_topic(request={"name": topic_path})
        except Exception as exc:
            if AlreadyExists is not None and isinstance(exc, AlreadyExists):
                pass
            else:
                message = str(exc)
                if "AlreadyExists" not in message and "409" not in message:
                    raise

    try:
        subscriber.create_subscription(request=build_subscription_request(config=cfg))
    except Exception as exc:
        if AlreadyExists is not None and isinstance(exc, AlreadyExists):
            pass
        else:
            message = str(exc)
            if "AlreadyExists" not in message and "409" not in message:
                raise

    return {
        "topic": cfg.topic_path,
        "subscription": cfg.subscription_path,
        "dead_letter_topic": cfg.dead_letter_topic_path,
    }


def _is_retryable_publish_exception(exc: Exception) -> bool:
    transient_types = tuple(
        exc_type
        for exc_type in (Aborted, DeadlineExceeded, InternalServerError, ResourceExhausted, ServiceUnavailable)
        if isinstance(exc_type, type)
    )
    if transient_types and isinstance(exc, transient_types):
        return True
    message = str(exc or "").lower()
    retry_markers = (
        "timeout",
        "temporar",
        "resource exhausted",
        "service unavailable",
        "deadline",
        "429",
        "502",
        "503",
        "504",
    )
    return any(marker in message for marker in retry_markers)


def publish_paper_check_job(
    job_id: str,
    *,
    reason: str = "created",
    priority: str = "normal",
    job_type: str = "fast",
    queue_partition: Optional[int] = None,
    config: Optional[PaperCheckPubSubConfig] = None,
) -> str:
    cfg = config or get_paper_check_pubsub_config()
    job_token = str(job_id or "").strip()
    if not job_token:
        raise PaperCheckPubSubError("job_id is required for Pub/Sub dispatch.")
    publisher = get_publisher_client()
    payload = json.dumps({"job_id": job_token}, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    last_error: Optional[Exception] = None
    for attempt in range(1, _PUBLISH_MAX_ATTEMPTS + 1):
        try:
            future = publisher.publish(
                cfg.topic_path,
                payload,
                job_id=job_token,
                reason=str(reason or "created"),
                priority=str(priority),
                job_type=str(job_type),
                queue_partition=str(queue_partition) if queue_partition is not None else "",
            )
            return str(future.result(timeout=_PUBLISH_TIMEOUT_SECONDS))
        except Exception as exc:
            last_error = exc
            should_retry = attempt < _PUBLISH_MAX_ATTEMPTS and _is_retryable_publish_exception(exc)
            if not should_retry:
                break
            delay = min(
                _PUBLISH_RETRY_MAX_DELAY_SECONDS,
                _PUBLISH_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)),
            ) + random.uniform(0.0, 0.05)
            logger.warning(
                "publish_paper_check_job retrying job_id=%s attempt=%s/%s backoff_s=%.3f error=%s",
                job_token,
                attempt,
                _PUBLISH_MAX_ATTEMPTS,
                delay,
                str(exc)[:240],
            )
            time.sleep(delay)
    raise PaperCheckPubSubError(
        f"Failed to publish paper check job '{job_token}' after {_PUBLISH_MAX_ATTEMPTS} attempts: {str(last_error)[:240]}"
    )


def parse_paper_check_message(data: bytes | str, attributes: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    if isinstance(data, bytes):
        raw = data.decode("utf-8")
    else:
        raw = str(data or "")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PaperCheckPubSubError("Invalid Pub/Sub message payload.") from exc
    if not isinstance(payload, dict):
        raise PaperCheckPubSubError("Pub/Sub message must be a JSON object.")
    job_id = str(payload.get("job_id") or "").strip()
    if not job_id:
        raise PaperCheckPubSubError("Pub/Sub message is missing job_id.")
    
    parsed = {"job_id": job_id}
    if attributes:
        parsed["priority"] = attributes.get("priority", "normal")
        parsed["job_type"] = attributes.get("job_type", "fast")
        pq = attributes.get("queue_partition")
        parsed["queue_partition"] = int(pq) if pq and pq.isdigit() else None
    return parsed
