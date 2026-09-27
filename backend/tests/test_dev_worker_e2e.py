"""
Priority 32 - End-to-end test for development Paper Check worker.

This test validates that the development worker automatically detects and processes
Paper Check jobs created through the real application.

NOTE: Full async worker E2E tests are difficult in pytest due to the worker's
long-running polling loop conflicting with pytest's async test management.
The worker's automatic job processing is validated through:
- Priority 36 browser E2E test (paper-check-e2e.spec.ts)
- Priority 37 comprehensive HTTP API validation

This test validates the worker's job processing logic directly without the polling loop.
"""

import asyncio
import os
import sys
import time
import pytest
from datetime import datetime, timezone
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set environment before any imports
os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8081"

from repositories.research import FirebaseResearchRepository, User
from services.paper_check_service import queue_paper_check_job
from workers.paper_check_worker import handle_job_trigger, WORKER_ID


def test_dev_worker_job_processing():
    """
    Test that the dev worker's job processing logic works correctly.
    
    This test validates the core job processing without the polling loop:
    1. Creates a user, workspace, and paper via repository
    2. Creates a Paper Check job via queue_paper_check_job
    3. Manually calls handle_job_trigger (simulating worker detection)
    4. Verifies the job reaches completed status with actual analysis result
    
    The automatic polling loop is validated through Priority 36 browser E2E test.
    """
    repo = FirebaseResearchRepository()
    
    # Create user
    user = repo.create_user(
        email="devworker-test@example.com",
        name="Dev Worker Test User",
        is_active=True,
        is_verified=True,
    )
    
    # Create workspace
    workspace = repo.create_workspace(
        user_id=user.id,
        name="Dev Worker Test Workspace",
        description="Test workspace for development worker validation"
    )
    
    # Create paper
    paper = repo.create_paper(
        workspace_id=workspace.id,
        title="Test Paper for Dev Worker",
        authors="Test Author",
        abstract="This is a test paper for development worker validation. The paper discusses embedding models including all-MiniLM-L6-v2 with 384-dimensional vectors and cosine similarity thresholds.",
        url="https://example.org/test-paper-dev-worker",
    )
    paper.doi = "10.1000/test-doi-dev-worker"
    paper.source = "manual"
    repo.save(paper)
    
    # Create Paper Check job (same as API endpoint would)
    job_data = queue_paper_check_job(
        repo=repo,
        user_id=user.id,
        paper_id=paper.id,
        workspace_id=workspace.id,
        raw_text="This is test raw text for Paper Check analysis. The paper discusses embedding models including all-MiniLM-L6-v2 with 384-dimensional vectors and cosine similarity thresholds.",
    )
    
    job_id = job_data.get("job_id")
    initial_status = job_data.get("status")
    
    assert job_id is not None, "Job ID should be returned"
    assert initial_status == "pending", f"Job should start as pending, got {initial_status}"
    
    # Manually trigger job processing (simulating worker detection)
    # This validates the core processing logic without the polling loop
    try:
        asyncio.run(handle_job_trigger(
            repo=repo,
            job_id=job_id,
            worker_id=WORKER_ID,
            job_timeout_seconds=120,
        ))
    except Exception as exc:
        pytest.fail(f"Job processing failed: {exc}")
    
    # Verify job completed
    final_job = repo.get_paper_check_job(job_id)
    assert final_job is not None, "Job should exist after processing"
    assert final_job.status == "completed", f"Job should be completed, got status: {final_job.status}"
    
    # Verify result is present and contains expected analysis
    result = final_job.result
    assert result is not None, "Completed job should have a result"
    assert isinstance(result, dict), "Result should be a dictionary"
    assert len(result) > 0, "Result should not be empty"
    
    # Note: Cleanup omitted to preserve the completed job for inspection


def test_dev_worker_multiple_jobs_sequential():
    """
    Test that the worker can process multiple jobs sequentially.
    
    This test validates sequential job processing without the polling loop.
    """
    repo = FirebaseResearchRepository()
    
    # Create user
    user = repo.create_user(
        email="devworker-multi@example.com",
        name="Dev Worker Multi Test",
        is_active=True,
        is_verified=True,
    )
    
    # Create workspace
    workspace = repo.create_workspace(
        user_id=user.id,
        name="Dev Worker Multi Workspace",
        description="Test workspace for multiple jobs"
    )
    
    # Create two papers
    paper1 = repo.create_paper(
        workspace_id=workspace.id,
        title="Test Paper 1",
        authors="Author 1",
        abstract="First test paper for multiple job validation.",
        url="https://example.org/paper1",
    )
    paper1.doi = "10.1000/paper1"
    paper1.source = "manual"
    repo.save(paper1)
    
    paper2 = repo.create_paper(
        workspace_id=workspace.id,
        title="Test Paper 2",
        authors="Author 2",
        abstract="Second test paper for multiple job validation.",
        url="https://example.org/paper2",
    )
    paper2.doi = "10.1000/paper2"
    paper2.source = "manual"
    repo.save(paper2)
    
    # Create two jobs
    job1_data = queue_paper_check_job(
        repo=repo,
        user_id=user.id,
        paper_id=paper1.id,
        workspace_id=workspace.id,
        raw_text="First paper raw text for analysis.",
    )
    job1_id = job1_data.get("job_id")
    
    job2_data = queue_paper_check_job(
        repo=repo,
        user_id=user.id,
        paper_id=paper2.id,
        workspace_id=workspace.id,
        raw_text="Second paper raw text for analysis.",
    )
    job2_id = job2_data.get("job_id")
    
    # Process jobs sequentially (simulating worker's sequential processing)
    for job_id in [job1_id, job2_id]:
        try:
            asyncio.run(handle_job_trigger(
                repo=repo,
                job_id=job_id,
                worker_id=WORKER_ID,
                job_timeout_seconds=120,
            ))
        except Exception as exc:
            pytest.fail(f"Job {job_id} processing failed: {exc}")
    
    # Verify both jobs completed
    job1_final = repo.get_paper_check_job(job1_id)
    job2_final = repo.get_paper_check_job(job2_id)
    
    assert job1_final.status == "completed", f"Job 1 should be completed, got: {job1_final.status}"
    assert job2_final.status == "completed", f"Job 2 should be completed, got: {job2_final.status}"
    
    assert job1_final.result is not None, "Job 1 should have result"
    assert job2_final.result is not None, "Job 2 should have result"
