from __future__ import annotations

import asyncio
import logging
from typing import Any

from services.rag_index_service import RAGIndexService
from services.rag_runtime import get_rag_runtime
from services.workspace_feed_service import queue_workspace_feed_job_best_effort
from services.workspace_insights_service import queue_workspace_insights_job_best_effort


logger = logging.getLogger(__name__)


def index_paper_best_effort(*, repo: Any, paper: Any) -> None:
    if paper is None:
        return
    workspace_id = int(getattr(paper, "workspace_id", 0) or 0)
    paper_id = int(getattr(paper, "id", 0) or 0)
    if workspace_id <= 0 or paper_id <= 0:
        return
    try:
        runtime = get_rag_runtime(db=getattr(repo, "db", None))
        index_service = RAGIndexService(runtime.embedding_service, runtime.vector_store)

        async def _run() -> None:
            await index_service.index_paper_record(paper)
            queue_workspace_insights_job_best_effort(
                repo=repo,
                workspace_id=workspace_id,
                trigger="post_indexing",
                reason=f"paper:{paper_id}",
            )
            queue_workspace_feed_job_best_effort(
                repo=repo,
                workspace_id=workspace_id,
                trigger="post_indexing",
                reason=f"paper:{paper_id}",
            )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(_run())
        else:
            loop.create_task(_run())
    except Exception as exc:
        logger.debug(
            "RAG paper index hook skipped for paper_id=%s workspace_id=%s: %s",
            paper_id,
            workspace_id,
            exc,
        )
