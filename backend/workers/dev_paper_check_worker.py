from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from repositories import ResearchRepository
from repositories.research import FirebaseResearchRepository
from workers.paper_check_worker import handle_job_trigger, WORKER_ID

logger = logging.getLogger(__name__)

_DEV_WORKER_ENABLED = os.getenv("PAPER_CHECK_DEV_WORKER_ENABLED", "0").strip().lower() in {"1", "true", "yes"}
_DEV_WORKER_POLL_INTERVAL = max(2.0, float(os.getenv("PAPER_CHECK_DEV_WORKER_POLL_INTERVAL", "5") or 5))
_DEV_WORKER_MAX_CONCURRENT = max(1, int(os.getenv("PAPER_CHECK_DEV_WORKER_MAX_CONCURRENT", "1") or 1))

_worker_task: Optional[asyncio.Task] = None
_active_jobs: set[str] = set()
_processing_lock = asyncio.Lock()
_thread_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dev_worker")


def is_dev_worker_enabled() -> bool:
    return _DEV_WORKER_ENABLED


async def start_dev_worker(repo: ResearchRepository):
    """Start the development Paper Check worker polling loop on the current event loop."""
    if not is_dev_worker_enabled():
        logger.info("dev_paper_check_worker: disabled by environment variable")
        return
    
    worker_id = f"dev-{WORKER_ID}"
    logger.info(
        json.dumps({
            "event": "dev_paper_check_worker_starting",
            "worker_id": worker_id,
            "poll_interval": _DEV_WORKER_POLL_INTERVAL,
            "max_concurrent": _DEV_WORKER_MAX_CONCURRENT,
        })
    )
    
    global _worker_task
    if _worker_task is not None and not _worker_task.done():
        logger.warning("dev_paper_check_worker: already running")
        return
    
    # Start worker as a background task on the current event loop
    _worker_task = asyncio.create_task(_poll_and_process_jobs(repo, worker_id))


async def stop_dev_worker():
    """Stop the development Paper Check worker polling loop."""
    global _worker_task
    if _worker_task is not None and not _worker_task.done():
        logger.info("dev_paper_check_worker: stopping")
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None
        logger.info("dev_paper_check_worker: stopped")
    
    # Shutdown thread pool
    _thread_pool.shutdown(wait=True)
    logger.info("dev_paper_check_worker: thread pool shutdown")


async def _process_single_job(
    repo: ResearchRepository,
    job_id: str,
    worker_id: str,
) -> Optional[str]:
    """Process a single Paper Check job using the existing handle_job_trigger."""
    try:
        await handle_job_trigger(
            repo=repo,
            job_id=job_id,
            worker_id=worker_id,
            job_timeout_seconds=120,
        )
        return job_id
    except Exception as exc:
        logger.exception(
            json.dumps({
                "event": "dev_paper_check_worker_job_failed",
                "job_id": job_id,
                "worker_id": worker_id,
                "error": str(exc),
            })
        )
        return None


async def _poll_and_process_jobs(repo: ResearchRepository, worker_id: str):
    """Poll for pending jobs and process them."""
    from datetime import timezone
    from google.cloud.firestore_v1.base_query import FieldFilter
    
    # Initial sleep to allow FastAPI startup to complete before first poll
    # This prevents blocking Firestore operations during application startup
    await asyncio.sleep(_DEV_WORKER_POLL_INTERVAL)
    
    # Helper function to run blocking Firestore operations in thread pool
    def _query_pending_jobs():
        return [
            snapshot.to_dict() or {}
            for snapshot in repo.paper_check_jobs.where(
                filter=FieldFilter("status", "==", "pending")
            ).stream()
        ]
    
    while True:
        try:
            # Get pending jobs directly from Firestore - run in thread pool to avoid blocking event loop
            loop = asyncio.get_running_loop()
            docs = await loop.run_in_executor(_thread_pool, _query_pending_jobs)
            
            if not docs:
                # No pending jobs, sleep
                await asyncio.sleep(_DEV_WORKER_POLL_INTERVAL)
                continue
            
            # Sort by created_at to process oldest first
            docs.sort(key=lambda doc: doc.get("created_at") or timezone.utc)
            
            # Process pending jobs one at a time
            for doc in docs:
                job_id = doc.get("job_id")
                if not job_id:
                    continue
                
                # Check if already processing this job
                async with _processing_lock:
                    if job_id in _active_jobs:
                        # Already processing, skip
                        break
                    if len(_active_jobs) >= _DEV_WORKER_MAX_CONCURRENT:
                        # Max concurrent reached, skip
                        break
                    _active_jobs.add(job_id)
                
                try:
                    # Process the job - handle_job_trigger does its own claiming
                    await _process_single_job(repo, job_id, worker_id)
                finally:
                    # Remove from active set
                    async with _processing_lock:
                        _active_jobs.discard(job_id)
                
                # Process one job per iteration to avoid concurrency issues
                break
            
            # Sleep after processing
            await asyncio.sleep(_DEV_WORKER_POLL_INTERVAL)
                
        except asyncio.CancelledError:
            logger.info("dev_paper_check_worker: polling loop cancelled")
            break
        except Exception as exc:
            logger.exception(
                json.dumps({
                    "event": "dev_paper_check_worker_polling_error",
                    "error": str(exc),
                })
            )
            await asyncio.sleep(_DEV_WORKER_POLL_INTERVAL)
