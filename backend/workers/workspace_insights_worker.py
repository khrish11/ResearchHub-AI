from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from uuid import uuid4


_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from repositories.research import FirebaseResearchRepository
from services.workspace_insights_service import (
    list_pending_workspace_insight_jobs,
    process_workspace_insights_job,
    recover_stuck_workspace_insight_jobs,
)


logger = logging.getLogger(__name__)

WORKER_ID = str(os.getenv("WORKSPACE_INSIGHTS_WORKER_ID") or uuid4().hex).strip()
POLL_INTERVAL_SECONDS = max(
    2.0,
    float(os.getenv("WORKSPACE_INSIGHTS_WORKER_POLL_INTERVAL_SECONDS", "6") or 6),
)
MAX_BATCH_SIZE = max(
    1,
    int(os.getenv("WORKSPACE_INSIGHTS_WORKER_BATCH_SIZE", "4") or 4),
)
RECOVERY_INTERVAL_SECONDS = max(
    10.0,
    float(os.getenv("WORKSPACE_INSIGHTS_WORKER_RECOVERY_INTERVAL_SECONDS", "30") or 30),
)
_LAST_RECOVERY_TS = 0.0


async def run_once(*, repo: FirebaseResearchRepository) -> int:
    global _LAST_RECOVERY_TS
    now = time.monotonic()
    if now - _LAST_RECOVERY_TS >= RECOVERY_INTERVAL_SECONDS:
        try:
            recovered = recover_stuck_workspace_insight_jobs(repo=repo)
            if recovered > 0:
                logger.warning("workspace_insights_worker recovered_stuck_jobs=%s", recovered)
        except Exception:
            logger.debug("workspace_insights_worker stuck recovery failed", exc_info=True)
        _LAST_RECOVERY_TS = now
    jobs = list_pending_workspace_insight_jobs(repo=repo, limit=MAX_BATCH_SIZE)
    if not jobs:
        return 0
    processed = 0
    for job in jobs:
        job_id = str(job.get("job_id") or "").strip()
        if not job_id:
            continue
        await process_workspace_insights_job(
            repo=repo,
            job_id=job_id,
            worker_id=WORKER_ID,
        )
        processed += 1
    return processed


async def run_forever() -> None:
    repo = FirebaseResearchRepository()
    logger.info(
        "workspace_insights_worker_started worker_id=%s poll_interval=%.1fs batch=%s",
        WORKER_ID,
        POLL_INTERVAL_SECONDS,
        MAX_BATCH_SIZE,
    )
    while True:
        try:
            processed = await run_once(repo=repo)
            if processed <= 0:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
        except Exception as exc:
            logger.exception("workspace_insights_worker_loop_error: %s", exc)
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    asyncio.run(run_forever())
