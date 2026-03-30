from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from repositories import ResearchRepository, get_research_repository
from repositories.research import User
from routers.auth import get_current_user
from services.rag_index_service import RAGIndexService
from services.rag_query_handler import RAGQueryInput
from services.rag_runtime import get_rag_runtime
from services.workspace_feed_service import queue_workspace_feed_job_best_effort
from services.workspace_insights_service import queue_workspace_insights_job_best_effort


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rag", tags=["rag"])


class RAGIndexWorkspaceRequest(BaseModel):
    workspace_id: int


class RAGIndexItem(BaseModel):
    source_id: str = Field(min_length=1, max_length=200)
    source_type: str = Field(default="unknown", min_length=1, max_length=60)
    text: str = Field(min_length=1, max_length=160000)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RAGIndexItemsRequest(BaseModel):
    workspace_id: int
    items: List[RAGIndexItem] = Field(default_factory=list, min_length=1, max_length=80)


class RAGRetrieveResponseItem(BaseModel):
    vector_id: str
    source_id: str
    source_type: str
    chunk_index: int
    text: str
    similarity_score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RAGQueryRequest(BaseModel):
    workspace_id: int
    query: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=6, ge=1, le=20)
    source_types: Optional[List[str]] = None
    min_similarity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_context_tokens: int = Field(default=1800, ge=300, le=5000)
    strict_grounding: bool = True


class RAGQueryResponseSource(BaseModel):
    source_id: str
    source_type: str
    title: Optional[str] = None
    mention_count: int = 0
    relevance_score: float = 0.0


class RAGQueryResponse(BaseModel):
    answer: str
    confidence: float
    grounding_score: float
    retrieved_count: int
    invalid_source_refs: List[int] = Field(default_factory=list)
    sources_used: List[RAGQueryResponseSource] = Field(default_factory=list)


def _ensure_workspace_access(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: int,
) -> None:
    workspace = repo.find_workspace_for_user(int(workspace_id), int(user_id))
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found.")


@router.post("/index/workspace")
async def index_workspace_content(
    payload: RAGIndexWorkspaceRequest,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _ensure_workspace_access(
        repo=repo,
        workspace_id=payload.workspace_id,
        user_id=int(current_user.id),
    )
    runtime = get_rag_runtime(db=getattr(repo, "db", None))
    index_service = RAGIndexService(
        runtime.embedding_service,
        runtime.vector_store,
    )
    stats = await index_service.index_workspace(
        repo=repo,
        workspace_id=payload.workspace_id,
        user_id=int(current_user.id),
    )
    queue_workspace_insights_job_best_effort(
        repo=repo,
        workspace_id=payload.workspace_id,
        user_id=int(current_user.id),
        trigger="workspace_indexed",
        reason="rag_index_workspace",
    )
    queue_workspace_feed_job_best_effort(
        repo=repo,
        workspace_id=payload.workspace_id,
        user_id=int(current_user.id),
        trigger="workspace_indexed",
        reason="rag_index_workspace",
    )
    return {
        "status": "ok",
        "workspace_id": payload.workspace_id,
        **stats.as_dict(),
    }


@router.post("/index/items")
async def index_custom_items(
    payload: RAGIndexItemsRequest,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _ensure_workspace_access(
        repo=repo,
        workspace_id=payload.workspace_id,
        user_id=int(current_user.id),
    )
    runtime = get_rag_runtime(db=getattr(repo, "db", None))
    index_service = RAGIndexService(
        runtime.embedding_service,
        runtime.vector_store,
    )
    stats = await index_service.index_ad_hoc_items(
        workspace_id=payload.workspace_id,
        items=[item.model_dump() for item in payload.items],
    )
    return {
        "status": "ok",
        "workspace_id": payload.workspace_id,
        **stats.as_dict(),
    }


@router.get("/retrieve")
async def retrieve_context(
    workspace_id: int = Query(..., ge=1),
    query: str = Query(..., min_length=2, max_length=2000),
    top_k: int = Query(6, ge=1, le=20),
    source_types: Optional[List[str]] = Query(default=None),
    min_similarity: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _ensure_workspace_access(
        repo=repo,
        workspace_id=workspace_id,
        user_id=int(current_user.id),
    )
    runtime = get_rag_runtime(db=getattr(repo, "db", None))
    results = await runtime.retrieval_service.retrieve(
        query=query,
        workspace_id=workspace_id,
        top_k=top_k,
        source_types=source_types,
        min_similarity=min_similarity,
    )
    return {
        "query": query,
        "workspace_id": workspace_id,
        "result_count": len(results),
        "results": [
            RAGRetrieveResponseItem(
                vector_id=item.vector_id,
                source_id=item.source_id,
                source_type=item.source_type,
                chunk_index=item.chunk_index,
                text=item.text,
                similarity_score=item.similarity_score,
                metadata=item.metadata,
            ).model_dump()
            for item in results
        ],
    }


@router.post("/query", response_model=RAGQueryResponse)
async def query_workspace(
    payload: RAGQueryRequest,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> RAGQueryResponse:
    _ensure_workspace_access(
        repo=repo,
        workspace_id=payload.workspace_id,
        user_id=int(current_user.id),
    )
    runtime = get_rag_runtime(db=getattr(repo, "db", None))

    results = await runtime.retrieval_service.retrieve(
        query=payload.query,
        workspace_id=payload.workspace_id,
        top_k=payload.top_k,
        source_types=payload.source_types,
        min_similarity=payload.min_similarity,
    )
    context_rows = [
        {
            "vector_id": item.vector_id,
            "source_id": item.source_id,
            "source_type": item.source_type,
            "text": item.text,
            "similarity_score": item.similarity_score,
            "metadata": item.metadata,
        }
        for item in runtime.retrieval_service.truncate_results_for_context(
            results, max_context_tokens=payload.max_context_tokens
        )
    ]

    output = await runtime.rag_query_handler.handle(
        RAGQueryInput(
            query=payload.query,
            retrieved_context=context_rows,
            strict_grounding=payload.strict_grounding,
            max_tokens=min(2200, payload.max_context_tokens + 300),
        ),
        db=getattr(repo, "db", None),
        user_id=str(current_user.id),
    )

    return RAGQueryResponse(
        answer=output.answer,
        confidence=output.confidence,
        grounding_score=output.grounding_score,
        retrieved_count=len(context_rows),
        invalid_source_refs=list(output.invalid_source_refs),
        sources_used=[
            RAGQueryResponseSource(
                source_id=source.source_id,
                source_type=source.source_type,
                title=source.title,
                mention_count=source.mention_count,
                relevance_score=source.relevance_score,
            )
            for source in output.sources_used
        ],
    )


@router.get("/status")
async def rag_status(
    workspace_id: int = Query(..., ge=1),
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _ensure_workspace_access(
        repo=repo,
        workspace_id=workspace_id,
        user_id=int(current_user.id),
    )
    runtime = get_rag_runtime(db=getattr(repo, "db", None))
    count = await runtime.vector_store.count_by_workspace(workspace_id)
    return {
        "workspace_id": workspace_id,
        "indexed_vectors": int(count),
        "ready": bool(count > 0),
    }
