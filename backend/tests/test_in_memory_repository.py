from __future__ import annotations

from datetime import datetime, timezone, timedelta
from repositories.research import (
    InMemoryResearchRepository,
    User,
    Workspace,
    Paper,
    Chat,
    SearchHistory,
    WorkspaceFile,
    DataRightsRequest,
    PaperCheckJob,
)


def test_in_memory_save_user_without_id_assigns_new_id() -> None:
    repo = InMemoryResearchRepository()

    user = User(
        id=None,
        email="google-user@test.com",
        google_id="google-sub-123",
        google_email="google-user@test.com",
        name="Google User",
        is_verified=True,
    )

    saved = repo.save(user)

    assert isinstance(saved, User)
    assert saved.id is not None
    assert int(saved.id) > 0

    fetched = repo.get_user_by_google_id("google-sub-123")
    assert fetched is not None
    assert fetched.id == saved.id


def test_chats_crud() -> None:
    repo = InMemoryResearchRepository()
    ws = repo.create_workspace(user_id=1, name="Workspace A")

    chat1 = repo.create_chat(workspace_id=ws.id, message="Hello", response="Hi there")
    chat2 = repo.create_chat(workspace_id=ws.id, message="How are you", response="I am good")

    assert repo.count_chats() == 2

    chats = repo.list_chats_for_workspace(ws.id, ascending=True)
    assert len(chats) == 2
    assert chats[0].message == "Hello"
    assert chats[1].message == "How are you"

    chats_desc = repo.list_chats_for_workspace(ws.id, ascending=False, limit=1)
    assert len(chats_desc) == 1
    assert chats_desc[0].message == "How are you"


def test_search_history_crud() -> None:
    repo = InMemoryResearchRepository()

    # Create search histories
    s1 = repo.record_search_history(
        user_id=1,
        query="Machine Learning",
        source="google",
        result_count=10,
    )
    assert s1.id is not None
    assert repo.count_search_history_for_user(1) == 1

    # Deduplication test (query matching within dedupe limit)
    s2 = repo.record_search_history(
        user_id=1,
        query="Machine Learning",
        source="google",
        result_count=15,
        dedupe_seconds=240,
    )
    # Should update existing instead of creating a new one
    assert s2.id == s1.id
    assert s2.result_count == 15
    assert repo.count_search_history_for_user(1) == 1

    # New search history with different query
    s3 = repo.record_search_history(
        user_id=1,
        query="Artificial Intelligence",
        source="google",
        result_count=20,
    )
    assert s3.id != s1.id
    assert repo.count_search_history_for_user(1) == 2

    # Delete single item
    repo.delete_search_history(user_id=1, item_id=s3.id)
    assert repo.count_search_history_for_user(1) == 1

    # Delete all search history for user
    repo.delete_search_history(user_id=1)
    assert repo.count_search_history_for_user(1) == 0


def test_workspace_files_crud() -> None:
    repo = InMemoryResearchRepository()
    ws = repo.create_workspace(user_id=1, name="Workspace A")
    paper = repo.create_paper(workspace_id=ws.id, title="Quantum Computing", authors="Einstein", abstract="")

    f1 = repo.create_workspace_file(
        workspace_id=ws.id,
        user_id=1,
        kind="pdf",
        filename="test.pdf",
        storage_bucket="bucket",
        storage_path="path/to/test.pdf",
        paper_id=paper.id,
    )

    assert f1.id is not None
    files = repo.list_workspace_files_for_workspace(workspace_id=ws.id, user_id=1)
    assert len(files) == 1
    assert files[0].filename == "test.pdf"

    fetched = repo.get_workspace_file_for_user(file_id=f1.id, workspace_id=ws.id, user_id=1)
    assert fetched is not None
    assert fetched.storage_path == "path/to/test.pdf"

    fetched_paper = repo.get_workspace_file_for_paper(paper_id=paper.id, workspace_id=ws.id, user_id=1)
    assert fetched_paper is not None
    assert fetched_paper.id == f1.id


def test_data_rights_requests() -> None:
    repo = InMemoryResearchRepository()

    req = repo.create_data_rights_request(
        user_id=1,
        email="test@test.com",
        request_type="delete",
        jurisdiction="gdpr",
        details="Please delete my data",
    )

    assert req.id is not None
    requests = repo.list_data_rights_requests_for_user(user_id=1)
    assert len(requests) == 1
    assert requests[0].request_type == "delete"


def test_paper_check_jobs_lifecycle() -> None:
    repo = InMemoryResearchRepository()

    job1 = repo.create_paper_check_job(
        job_id="job_abc",
        user_id=1,
        paper_id=101,
        fingerprint="fp1",
        input_data={"data": "test"},
        status="pending",
    )

    assert job1.job_id == "job_abc"
    assert repo.get_paper_check_job("job_abc") == job1

    # Claim next pending job
    claimed = repo.claim_next_job(worker_id="worker_1")
    assert claimed is not None
    assert claimed.job_id == "job_abc"
    assert claimed.status == "running"
    assert claimed.claimed_by == "worker_1"

    # Verify active jobs count
    assert repo.count_active_jobs_for_user(user_id=1) == 1

    # Try to claim again when none are pending
    assert repo.claim_next_job(worker_id="worker_2") is None

    # Complete the job
    completed = repo.complete_paper_check_job(
        job_id="job_abc",
        worker_id="worker_1",
        claimed_at=claimed.claimed_at,
        result={"quality": "high"},
    )
    assert completed is not None
    assert completed.status == "completed"
    assert completed.result == {"quality": "high"}

    # Latest job search
    latest = repo.find_latest_paper_check_job(paper_id=101, user_id=1)
    assert latest is not None
    assert latest.job_id == "job_abc"

    # Reusable job lookup
    reusable = repo.find_reusable_paper_check_job(user_id=1, fingerprint="fp1")
    assert reusable is not None
    assert reusable.job_id == "job_abc"

    # Metrics
    metrics = repo.get_paper_check_job_metrics(timeout_seconds=60)
    assert metrics["jobs_completed"] == 1
    assert metrics["jobs_running"] == 0

    # Stuck jobs recovery test
    job2 = repo.create_paper_check_job(
        job_id="job_def",
        user_id=1,
        paper_id=102,
        input_data={"data": "test2"},
        status="running",
        claimed_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    stuck = repo.get_stuck_jobs(timeout_seconds=300)
    assert len(stuck) == 1
    assert stuck[0].job_id == "job_def"

    # Fail job with retryable
    failed_requeue = repo.fail_or_requeue_paper_check_job(
        job_id="job_def",
        worker_id=None,
        claimed_at=None,
        error_message="Fail message",
        retryable=True,
    )
    assert failed_requeue is not None
    assert failed_requeue.status == "pending"
    assert failed_requeue.retry_count == 1


def test_cascade_delete() -> None:
    repo = InMemoryResearchRepository()

    user = repo.create_user(email="test@user.com")
    ws = repo.create_workspace(user_id=user.id, name="My Workspace")
    paper = repo.create_paper(workspace_id=ws.id, title="P1", authors="A1", abstract="")
    repo.create_chat(workspace_id=ws.id, message="M1", response="R1")
    repo.create_workspace_file(
        workspace_id=ws.id,
        user_id=user.id,
        kind="pdf",
        filename="f1.pdf",
        storage_bucket="b1",
        storage_path="p1",
    )
    repo.create_docspace_document(workspace_id=ws.id, user_id=user.id, title="Notes")

    assert repo.count_users() == 1
    assert repo.count_workspaces() == 1
    assert repo.count_papers() == 1
    assert repo.count_chats() == 1

    # Perform cascade delete on user account
    repo.delete_user_account(user.id)

    assert repo.count_users() == 0
    assert repo.count_workspaces() == 0
    assert repo.count_papers() == 0
    assert repo.count_chats() == 0
