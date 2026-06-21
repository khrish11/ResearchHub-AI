from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from repositories.research import FirebaseResearchRepository, User
from services import paper_check_service
from services.paper_check_service import get_paper_check_metrics_snapshot
from workers.paper_check_worker import handle_job_trigger


def _create_workspace_and_paper(
    repo: FirebaseResearchRepository,
    user: User,
    *,
    title: str = "Reliable Graph Detection",
    authors: str = "Alice Smith, Bob Chen",
    abstract: str = "This study evaluates graph anomaly detection under constrained settings.",
):
    workspace = repo.create_workspace(user.id, "Citation WS", "Workspace for citation tests")
    paper = repo.create_paper(
        workspace_id=workspace.id,
        title=title,
        authors=authors,
        abstract=abstract,
        url="https://example.org/papers/reliable-graph-detection",
    )
    paper.doi = "10.1000/example-doi"
    paper.source = "OpenAlex"
    repo.save(paper)
    return workspace, paper


def _poll_paper_check_job(
    test_client: TestClient,
    auth_headers: dict,
    job_id: str,
    *,
    timeout_seconds: float = 6.0,
    interval_seconds: float = 0.15,
    path_template: str = "/research/paper-check/{job_id}",
):
    deadline = time.time() + timeout_seconds
    last_payload = None
    while time.time() < deadline:
        response = test_client.get(
            path_template.format(job_id=job_id),
            headers=auth_headers,
        )
        assert response.status_code == 200
        payload = response.json()
        last_payload = payload
        if payload.get("status") in {"completed", "failed"}:
            return payload
        time.sleep(interval_seconds)
    raise AssertionError(f"Paper check job {job_id} did not finish in time: {last_payload}")


def test_post_citation_returns_structured_payload(
    test_client: TestClient,
    auth_headers: dict,
):
    response = test_client.post(
        "/papers/citation",
        json={
            "title": "Reliable Graph Detection",
            "authors": ["Alice Smith", "Bob Chen"],
            "year": "2024",
            "venue": "Journal of Reliable Systems",
            "url": "https://example.org/papers/reliable-graph-detection",
            "style": "apa",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["style"] == "apa"
    assert isinstance(data["citation"], str) and "Reliable Graph Detection" in data["citation"]
    assert isinstance(data["completeness_score"], int)
    assert isinstance(data["missing_fields"], list)
    assert isinstance(data["warnings"], list)


def test_mla_citation(
    test_client: TestClient,
    auth_headers: dict,
):
    response = test_client.post(
        "/papers/citation",
        json={
            "title": "Reliable Graph Detection",
            "authors": ["Alice Smith", "Bob Chen", "Cara Diaz"],
            "year": "2024",
            "venue": "Journal of Reliable Systems",
            "url": "https://example.org/papers/reliable-graph-detection",
            "style": "mla",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["style"] == "mla"
    assert "Reliable Graph Detection" in data["citation"]
    assert "et al." in data["citation"]


def test_ieee_citation(
    test_client: TestClient,
    auth_headers: dict,
):
    response = test_client.post(
        "/papers/citation",
        json={
            "title": "Reliable Graph Detection",
            "authors": ["Alice Smith", "Bob Chen"],
            "year": "2024",
            "venue": "Journal of Reliable Systems",
            "doi": "10.1000/example-doi",
            "style": "ieee",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["style"] == "ieee"
    assert "Reliable Graph Detection" in data["citation"]
    assert "2024" in data["citation"]


def test_chicago_citation(
    test_client: TestClient,
    auth_headers: dict,
):
    response = test_client.post(
        "/papers/citation",
        json={
            "title": "Reliable Graph Detection",
            "authors": ["Alice Smith", "Bob Chen"],
            "year": "2024",
            "venue": "Journal of Reliable Systems",
            "style": "chicago",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["style"] == "chicago"
    assert "Reliable Graph Detection" in data["citation"]
    assert "(2024)" in data["citation"]


def test_get_paper_citation_uses_saved_paper(
    test_client: TestClient,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
):
    _, paper = _create_workspace_and_paper(repo, mock_user)

    response = test_client.get(
        f"/papers/{paper.id}/citation",
        params={"style": "ieee"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["style"] == "ieee"
    assert "Reliable Graph Detection" in data["citation"]
    assert data["metadata"]["doi"] == "10.1000/example-doi"


def test_workspace_bibtex_export(
    test_client: TestClient,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    monkeypatch.setattr("routers.workspaces.storage_is_configured", lambda: False)
    workspace, _paper = _create_workspace_and_paper(repo, mock_user)
    repo.create_paper(
        workspace_id=workspace.id,
        title="Second Reference Paper",
        authors="Dana Liu, Evan Park",
        abstract="A companion paper used to verify workspace exports include all papers.",
    )

    response = test_client.get(
        f"/workspaces/{workspace.id}/export",
        params={"format": "bibtex"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.text
    assert body.count("@") == 2
    assert "Reliable Graph Detection" in body
    assert "Second Reference Paper" in body


def test_latest_paper_check_job_returns_completed_job(
    test_client: TestClient,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
):
    workspace, paper = _create_workspace_and_paper(repo, mock_user)
    job = repo.create_paper_check_job(
        job_id="job-latest-completed",
        user_id=int(mock_user.id or 0),
        paper_id=paper.id,
        input_data={"workspace_id": workspace.id},
        status="completed",
        result={"paper_analysis": {"snapshot": {"summary": "latest"}}},
        processing_completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    response = test_client.get(
        "/research/paper-check/latest",
        params={"paper_id": paper.id, "workspace_id": workspace.id},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job.job_id
    assert data["status"] == "completed"
    assert data["result"]["paper_analysis"]["snapshot"]["summary"] == "latest"


def test_latest_paper_check_job_selects_newest_completed(
    test_client: TestClient,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
):
    workspace, paper = _create_workspace_and_paper(repo, mock_user)
    repo.create_paper_check_job(
        job_id="job-old-completed",
        user_id=int(mock_user.id or 0),
        paper_id=paper.id,
        input_data={"workspace_id": workspace.id},
        status="completed",
        result={"paper_analysis": {"snapshot": {"summary": "old"}}},
        processing_completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    repo.create_paper_check_job(
        job_id="job-running-newer",
        user_id=int(mock_user.id or 0),
        paper_id=paper.id,
        input_data={"workspace_id": workspace.id},
        status="running",
        claimed_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    repo.create_paper_check_job(
        job_id="job-new-completed",
        user_id=int(mock_user.id or 0),
        paper_id=paper.id,
        input_data={"workspace_id": workspace.id},
        status="completed",
        result={"paper_analysis": {"snapshot": {"summary": "new"}}},
        processing_completed_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )

    response = test_client.get(
        "/research/paper-check/latest",
        params={"paper_id": paper.id, "workspace_id": workspace.id},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "job-new-completed"
    assert data["result"]["paper_analysis"]["snapshot"]["summary"] == "new"


def test_latest_paper_check_job_returns_404_when_missing(
    test_client: TestClient,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
):
    workspace, paper = _create_workspace_and_paper(repo, mock_user)

    response = test_client.get(
        "/research/paper-check/latest",
        params={"paper_id": paper.id, "workspace_id": workspace.id},
        headers=auth_headers,
    )

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "job_not_found"


def test_paper_check_raw_text_falls_back_without_ai_service(
    test_client: TestClient,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    monkeypatch,
):
    monkeypatch.setattr(paper_check_service, "groq_client", None)
    published: list[str] = []

    def _publish(job_id: str, *, reason: str = "created", **kwargs):
        published.append(job_id)
        return f"msg-{len(published)}"

    monkeypatch.setattr(paper_check_service, "publish_paper_check_job", _publish)

    raw_text = (
        "Introduction\n\n"
        "This paper presents a comprehensive evaluation of graph anomaly detection. "
        "This paper presents robust results across multiple constrained settings. "
        "Furthermore, this paper presents promising results with low citation grounding.\n\n"
        "Conclusion\n\n"
        "Future work includes stronger ablations and dataset transparency."
    )

    response = test_client.post(
        "/research/paper-check",
        json={"raw_text": raw_text},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert isinstance(data["job_id"], str) and data["job_id"]

    assert published == [data["job_id"]]
    asyncio.run(handle_job_trigger(repo=repo, job_id=data["job_id"], worker_id="test-worker"))
    completed = _poll_paper_check_job(
        test_client,
        auth_headers,
        data["job_id"],
    )

    assert completed["status"] == "completed"
    result = completed["result"]
    assert result["paper_analysis"]["snapshot"]["summary"].startswith("Heuristic fallback")
    assert result["ai_writing_likelihood"]["disclaimer"].startswith("This analysis is advisory")
    assert result["metadata"]["model_used"] is None


def test_paper_check_failure_marks_job_failed(
    test_client: TestClient,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    monkeypatch,
):
    async def _explode(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(paper_check_service, "run_paper_check", _explode)
    published: list[tuple[str, str]] = []

    def _publish(job_id: str, *, reason: str = "created", **kwargs):
        published.append((job_id, reason))
        return f"msg-{len(published)}"

    monkeypatch.setattr(paper_check_service, "publish_paper_check_job", _publish)

    response = test_client.post(
        "/research/paper-check",
        json={"raw_text": "This draft should fail."},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    repo.update_job_status(data["job_id"], {"max_retries": 0})

    asyncio.run(handle_job_trigger(repo=repo, job_id=data["job_id"], worker_id="test-worker", publisher=_publish))
    failed = _poll_paper_check_job(
        test_client,
        auth_headers,
        data["job_id"],
    )

    assert failed["status"] == "failed"
    assert failed["error"]["message"] == "boom"
    assert failed["error"]["retryable"] is True
    assert failed["result"] is None
    assert published and published[0] == (data["job_id"], "created")


def test_duplicate_job_detection_returns_existing_job(
    test_client: TestClient,
    auth_headers: dict,
    monkeypatch,
):
    published: list[tuple[str, str]] = []

    def _publish(job_id: str, *, reason: str = "created", **kwargs):
        published.append((job_id, reason))
        return f"msg-{len(published)}"

    monkeypatch.setattr(paper_check_service, "publish_paper_check_job", _publish)
    payload = {
        "raw_text": "Introduction\n\nDuplicate detection test.\n\nConclusion\n\nDone.",
        "workspace_id": 7,
    }

    first = test_client.post("/research/paper-check", json=payload, headers=auth_headers)
    second = test_client.post("/research/paper-check", json=payload, headers=auth_headers)

    assert first.status_code == 200
    assert second.status_code == 200
    first_data = first.json()
    second_data = second.json()
    assert first_data["status"] == "pending"
    assert second_data["status"] == "pending"
    assert first_data["job_id"] == second_data["job_id"]
    assert published == [
        (first_data["job_id"], "created"),
        (first_data["job_id"], "deduplicated_pending"),
    ]


def test_completed_result_is_reused_for_matching_fingerprint(
    test_client: TestClient,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    monkeypatch,
):
    monkeypatch.setattr(paper_check_service, "groq_client", None)
    published: list[str] = []

    def _publish(job_id: str, *, reason: str = "created", **kwargs):
        published.append(job_id)
        return f"msg-{len(published)}"

    monkeypatch.setattr(paper_check_service, "publish_paper_check_job", _publish)
    payload = {
        "raw_text": "Introduction\n\nResult reuse test paragraph.\n\nConclusion\n\nDone.",
        "workspace_id": 9,
    }

    first = test_client.post("/research/paper-check", json=payload, headers=auth_headers)
    assert first.status_code == 200
    first_job_id = first.json()["job_id"]

    asyncio.run(handle_job_trigger(repo=repo, job_id=first_job_id, worker_id="reuse-worker"))

    reused = test_client.post("/research/paper-check", json=payload, headers=auth_headers)
    assert reused.status_code == 200
    reused_data = reused.json()
    assert reused_data["status"] == "completed"
    assert reused_data["job_id"] == first_job_id
    assert reused_data["paper_analysis"]["snapshot"]["summary"].startswith("Heuristic fallback")


def test_metrics_tracking_reports_created_completed_and_latency(
    test_client: TestClient,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    monkeypatch,
):
    monkeypatch.setattr(paper_check_service, "groq_client", None)
    published: list[str] = []

    def _publish(job_id: str, *, reason: str = "created", **kwargs):
        published.append(job_id)
        return f"msg-{len(published)}"

    monkeypatch.setattr(paper_check_service, "publish_paper_check_job", _publish)
    response = test_client.post(
        "/research/paper-check",
        json={"raw_text": "Introduction\n\nMetrics test paragraph.\n\nConclusion\n\nDone."},
        headers=auth_headers,
    )
    assert response.status_code == 200

    asyncio.run(handle_job_trigger(repo=repo, job_id=response.json()["job_id"], worker_id="metrics-worker"))
    metrics = get_paper_check_metrics_snapshot(repo=repo)

    assert metrics["total_jobs_created"] == 1
    assert metrics["jobs_completed"] == 1
    assert metrics["jobs_failed"] == 0
    assert metrics["avg_latency_ms"] >= 0


def test_paper_check_legacy_status_endpoint_supports_polling(
    test_client: TestClient,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    monkeypatch,
):
    monkeypatch.setattr(paper_check_service, "groq_client", None)
    published: list[str] = []

    def _publish(job_id: str, *, reason: str = "created", **kwargs):
        published.append(job_id)
        return f"msg-{len(published)}"

    monkeypatch.setattr(paper_check_service, "publish_paper_check_job", _publish)

    response = test_client.post(
        "/research/paper-check",
        json={"raw_text": "Introduction\n\nA concise test paragraph.\n\nConclusion\n\nDone."},
        headers=auth_headers,
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]

    asyncio.run(handle_job_trigger(repo=repo, job_id=job_id, worker_id="legacy-worker"))
    completed = _poll_paper_check_job(
        test_client,
        auth_headers,
        job_id,
        path_template="/research/paper-check/jobs/{job_id}",
    )

    assert completed["job_id"] == job_id
    assert completed["status"] == "completed"


def test_admin_can_requeue_failed_job(
    test_client: TestClient,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    published: list[tuple[str, str]] = []

    def _publish(job_id: str, *, reason: str = "created", **kwargs):
        published.append((job_id, reason))
        return f"msg-{len(published)}"

    async def _explode(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(paper_check_service, "publish_paper_check_job", _publish)
    monkeypatch.setattr(paper_check_service, "run_paper_check", _explode)
    monkeypatch.setenv("ADMIN_USER_IDS", str(mock_user.id))

    response = test_client.post(
        "/research/paper-check",
        json={"raw_text": "Introduction\n\nAdmin requeue.\n\nConclusion\n\nDone."},
        headers=auth_headers,
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    repo.update_job_status(job_id, {"max_retries": 0})

    asyncio.run(handle_job_trigger(repo=repo, job_id=job_id, worker_id="requeue-worker", publisher=_publish))
    failed = _poll_paper_check_job(test_client, auth_headers, job_id)
    assert failed["status"] == "failed"

    requeue = test_client.post(
        f"/research/paper-check/{job_id}/requeue",
        headers=auth_headers,
    )
    assert requeue.status_code == 200
    data = requeue.json()
    assert data["job_id"] == job_id
    assert data["status"] == "pending"
    assert published[-1] == (job_id, "admin_requeue")


def test_partition_fairness(
    test_client: TestClient,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    monkeypatch,
):
    monkeypatch.setattr(paper_check_service, "QUEUE_PARTITION_COUNT", 4)
    partitions = set()
    for i in range(10):
        response = test_client.post(
            "/research/paper-check",
            json={"raw_text": f"Partition test {i}"},
            headers=auth_headers,
        )
        job_id = response.json()["job_id"]
        job = repo.get_paper_check_job(job_id)
        if job.queue_partition is not None:
            partitions.add(job.queue_partition)
    
    assert len(partitions) > 1, f"Expected multiple partitions, got {partitions}"


def test_burst_handling(
    test_client: TestClient,
    auth_headers: dict,
    monkeypatch,
):
    monkeypatch.setattr(paper_check_service, "_PUBLISH_RATE_LIMIT_TOKENS", 2.0)
    paper_check_service._RATE_LIMIT_STATE["tokens"] = 2.0
    
    published_count = 0
    def _publish(*args, **kwargs):
        nonlocal published_count
        published_count += 1
        return f"msg-{published_count}"
        
    monkeypatch.setattr(paper_check_service, "publish_paper_check_job", _publish)
    
    for _ in range(5):
        test_client.post("/research/paper-check", json={"raw_text": "burst"}, headers=auth_headers)
        
    assert published_count == 2


def test_priority_scheduling(
    test_client: TestClient,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    monkeypatch,
):
    from workers.paper_check_worker import redispatch_pending_jobs
    
    published_jobs = []
    def _publish(job_id: str, **kwargs):
        published_jobs.append(job_id)
        return "msg-id"
        
    monkeypatch.setattr(paper_check_service, "publish_paper_check_job", lambda *args, **kwargs: None)
    
    jobs = []
    for prio in ["low", "normal", "high"]:
        res = test_client.post("/research/paper-check", json={"raw_text": prio}, headers=auth_headers)
        job_id = res.json()["job_id"]
        # Force the properties we want testing directly in db
        repo.update_job_status(job_id, {"priority": prio, "status": "pending"})
        jobs.append((job_id, prio))

    # wait a tiny bit to simulate time passing if limits are strict, wait no we just use older_than_seconds=-1
    asyncio.run(redispatch_pending_jobs(repo=repo, older_than_seconds=-1, limit=2, publisher=_publish))
    
    assert len(published_jobs) == 2
    # Ensure high and normal priorities were taken first
    assert jobs[2][0] in published_jobs  # high
    assert jobs[1][0] in published_jobs  # normal

