from __future__ import annotations

import pytest
from types import SimpleNamespace

from utils import paper_check_pubsub


def test_subscription_request_contains_dead_letter_policy(monkeypatch):
    class _DeadLetterPolicy:
        def __init__(self, *, dead_letter_topic: str, max_delivery_attempts: int):
            self.dead_letter_topic = dead_letter_topic
            self.max_delivery_attempts = max_delivery_attempts

    monkeypatch.setattr(
        paper_check_pubsub,
        "pubsub_v1",
        SimpleNamespace(types=SimpleNamespace(DeadLetterPolicy=_DeadLetterPolicy)),
    )
    config = paper_check_pubsub.PaperCheckPubSubConfig(
        project_id="demo-project",
        topic_id="paper-check-jobs",
        subscription_id="paper-check-jobs-sub",
        dead_letter_topic_id="paper-check-jobs-dlq",
        max_delivery_attempts=7,
        ack_deadline_seconds=120,
    )

    request = paper_check_pubsub.build_subscription_request(config=config)

    assert request["topic"] == "projects/demo-project/topics/paper-check-jobs"
    assert request["name"] == "projects/demo-project/subscriptions/paper-check-jobs-sub"
    assert request["dead_letter_policy"].dead_letter_topic == "projects/demo-project/topics/paper-check-jobs-dlq"
    assert request["dead_letter_policy"].max_delivery_attempts == 7


def test_publish_job_retries_then_succeeds(monkeypatch):
    attempts = {"count": 0}

    class _Future:
        def result(self, timeout=None):  # type: ignore[no-untyped-def]
            return "msg-123"

    class _Publisher:
        def publish(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("service unavailable")
            return _Future()

    config = paper_check_pubsub.PaperCheckPubSubConfig(
        project_id="demo-project",
        topic_id="paper-check-jobs",
        subscription_id="paper-check-jobs-sub",
        dead_letter_topic_id="paper-check-jobs-dlq",
        max_delivery_attempts=7,
        ack_deadline_seconds=120,
    )
    monkeypatch.setattr(paper_check_pubsub, "get_publisher_client", lambda: _Publisher())
    monkeypatch.setattr(paper_check_pubsub, "_PUBLISH_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(paper_check_pubsub.time, "sleep", lambda *_args, **_kwargs: None)

    message_id = paper_check_pubsub.publish_paper_check_job("job-1", config=config)

    assert message_id == "msg-123"
    assert attempts["count"] == 2


def test_publish_job_raises_after_max_retries(monkeypatch):
    class _Publisher:
        def publish(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("503 upstream unavailable")

    config = paper_check_pubsub.PaperCheckPubSubConfig(
        project_id="demo-project",
        topic_id="paper-check-jobs",
        subscription_id="paper-check-jobs-sub",
        dead_letter_topic_id="paper-check-jobs-dlq",
        max_delivery_attempts=7,
        ack_deadline_seconds=120,
    )
    monkeypatch.setattr(paper_check_pubsub, "get_publisher_client", lambda: _Publisher())
    monkeypatch.setattr(paper_check_pubsub, "_PUBLISH_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(paper_check_pubsub.time, "sleep", lambda *_args, **_kwargs: None)

    with pytest.raises(paper_check_pubsub.PaperCheckPubSubError):
        paper_check_pubsub.publish_paper_check_job("job-2", config=config)
