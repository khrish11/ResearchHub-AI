from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from repositories import ResearchRepository, get_research_repository
from repositories.research import User
from routers.auth import get_current_user
from services.workspace_feed_service import (
    WORKSPACE_FEED_DISCLAIMER,
    get_or_generate_workspace_feed,
    get_workspace_feed_job,
    get_workspace_feed_page,
    mark_workspace_feed_item_read,
)


router = APIRouter(prefix="/workspace-feed", tags=["workspace-feed"])
logger = logging.getLogger(__name__)


def _to_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    text = str(value).strip()
    return text or None


def _require_workspace_access(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: int,
) -> None:
    workspace = repo.find_workspace_for_user(int(workspace_id), int(user_id))
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found.")


class WorkspaceFeedSource(BaseModel):
    source_index: int = 0
    source_id: str = ""
    source_type: str = ""
    title: str = ""
    url: str = ""
    doi: str = ""
    paper_id: int = 0
    similarity_score: float = 0.0


class WorkspaceFeedItem(BaseModel):
    feed_item_id: str
    type: str
    title: str
    description: str
    related_papers: List[int] = Field(default_factory=list)
    importance_score: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    read: bool = False
    read_at: Optional[str] = None
    source_refs: List[int] = Field(default_factory=list)
    sources: List[WorkspaceFeedSource] = Field(default_factory=list)


class WorkspaceFeedResponse(BaseModel):
    status: str
    workspace_id: int
    disclaimer: str = WORKSPACE_FEED_DISCLAIMER
    items: List[WorkspaceFeedItem] = Field(default_factory=list)
    next_cursor: Optional[str] = None
    total_count: int = 0
    unread_count: int = 0
    job_id: Optional[str] = None
    job_status: Optional[str] = None
    error: Optional[str] = None


class WorkspaceFeedJobResponse(BaseModel):
    job_id: str
    status: str
    workspace_id: int
    user_id: int
    trigger: str = ""
    reason: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WorkspaceFeedReadRequest(BaseModel):
    read: bool = True


def _map_item(raw: Dict[str, Any]) -> WorkspaceFeedItem:
    raw_sources = raw.get("sources") if isinstance(raw.get("sources"), list) else []
    sources: List[WorkspaceFeedSource] = []
    for source in raw_sources:
        if not isinstance(source, dict):
            continue
        sources.append(
            WorkspaceFeedSource(
                source_index=int(source.get("source_index") or 0),
                source_id=str(source.get("source_id") or ""),
                source_type=str(source.get("source_type") or ""),
                title=str(source.get("title") or ""),
                url=str(source.get("url") or ""),
                doi=str(source.get("doi") or ""),
                paper_id=int(source.get("paper_id") or 0),
                similarity_score=float(source.get("similarity_score") or 0.0),
            )
        )
    return WorkspaceFeedItem(
        feed_item_id=str(raw.get("feed_item_id") or ""),
        type=str(raw.get("type") or "recommendation"),
        title=str(raw.get("title") or ""),
        description=str(raw.get("description") or ""),
        related_papers=[int(item) for item in (raw.get("related_papers") or []) if int(item) > 0],
        importance_score=float(raw.get("importance_score") or 0.0),
        created_at=_to_iso(raw.get("created_at")),
        updated_at=_to_iso(raw.get("updated_at")),
        read=bool(raw.get("read")),
        read_at=_to_iso(raw.get("read_at")),
        source_refs=[int(item) for item in (raw.get("source_refs") or []) if int(item) > 0],
        sources=sources,
    )


@router.get("/jobs/{job_id}", response_model=WorkspaceFeedJobResponse)
def workspace_feed_job_status(
    job_id: str,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> WorkspaceFeedJobResponse:
    row = get_workspace_feed_job(repo=repo, job_id=job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Workspace feed job not found.")
    if int(row.get("user_id") or 0) != int(current_user.id):
        raise HTTPException(status_code=404, detail="Workspace feed job not found.")
    return WorkspaceFeedJobResponse(
        job_id=str(row.get("job_id") or job_id),
        status=str(row.get("status") or "unknown"),
        workspace_id=int(row.get("workspace_id") or 0),
        user_id=int(row.get("user_id") or 0),
        trigger=str(row.get("trigger") or ""),
        reason=str(row.get("reason") or ""),
        result=row.get("result") if isinstance(row.get("result"), dict) else None,
        error=str(row.get("error") or "") or None,
        created_at=_to_iso(row.get("created_at")),
        updated_at=_to_iso(row.get("updated_at")),
    )


def _build_feed_response(
    *,
    status: str,
    workspace_id: int,
    page: Dict[str, Any],
    job: Optional[Dict[str, Any]],
) -> WorkspaceFeedResponse:
    raw_items = page.get("items") if isinstance(page.get("items"), list) else []
    items = [_map_item(row) for row in raw_items if isinstance(row, dict)]
    return WorkspaceFeedResponse(
        status=str(status or "unknown"),
        workspace_id=workspace_id,
        disclaimer=WORKSPACE_FEED_DISCLAIMER,
        items=items,
        next_cursor=str(page.get("next_cursor")) if page.get("next_cursor") is not None else None,
        total_count=int(page.get("total_count") or 0),
        unread_count=int(page.get("unread_count") or 0),
        job_id=str(job.get("job_id")) if isinstance(job, dict) and job.get("job_id") else None,
        job_status=str(job.get("status")) if isinstance(job, dict) and job.get("status") else None,
        error=str(job.get("error")) if isinstance(job, dict) and job.get("error") else None,
    )


@router.get("/{workspace_id}", response_model=WorkspaceFeedResponse)
async def get_workspace_feed(
    workspace_id: int,
    refresh: bool = Query(False),
    run_inline: bool = Query(True),
    sort: str = Query("importance"),
    limit: int = Query(15, ge=1, le=50),
    cursor: Optional[str] = Query(default=None),
    include_read: bool = Query(True),
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> WorkspaceFeedResponse:
    _require_workspace_access(
        repo=repo,
        workspace_id=workspace_id,
        user_id=int(current_user.id),
    )
    try:
        generated = await get_or_generate_workspace_feed(
            repo=repo,
            workspace_id=workspace_id,
            user_id=int(current_user.id),
            refresh=bool(refresh),
            run_inline=bool(run_inline),
            trigger="dashboard_open" if not refresh else "manual_refresh",
        )
    except Exception as exc:
        logger.exception(
            "workspace_feed_get_failed workspace_id=%s user_id=%s",
            workspace_id,
            current_user.id,
        )
        generated = {
            "status": "failed",
            "job": {"status": "failed", "error": str(exc) or "Workspace feed request failed."},
        }
    try:
        page = get_workspace_feed_page(
            repo=repo,
            workspace_id=workspace_id,
            user_id=int(current_user.id),
            sort=sort,
            limit=limit,
            cursor=cursor,
            include_read=bool(include_read),
        )
    except Exception as exc:
        logger.exception(
            "workspace_feed_page_failed workspace_id=%s user_id=%s",
            workspace_id,
            current_user.id,
        )
        page = {"items": [], "next_cursor": None, "total_count": 0, "unread_count": 0}
        if not isinstance(generated.get("job"), dict):
            generated["job"] = {}
        generated["job"]["status"] = "failed"
        generated["job"]["error"] = str(exc) or "Workspace feed listing failed."
    return _build_feed_response(
        status=str(generated.get("status") or "unknown"),
        workspace_id=workspace_id,
        page=page,
        job=generated.get("job") if isinstance(generated.get("job"), dict) else None,
    )


@router.post("/{workspace_id}/refresh", response_model=WorkspaceFeedResponse)
async def refresh_workspace_feed(
    workspace_id: int,
    run_inline: bool = Query(True),
    sort: str = Query("importance"),
    limit: int = Query(15, ge=1, le=50),
    cursor: Optional[str] = Query(default=None),
    include_read: bool = Query(True),
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> WorkspaceFeedResponse:
    _require_workspace_access(
        repo=repo,
        workspace_id=workspace_id,
        user_id=int(current_user.id),
    )
    try:
        generated = await get_or_generate_workspace_feed(
            repo=repo,
            workspace_id=workspace_id,
            user_id=int(current_user.id),
            refresh=True,
            run_inline=bool(run_inline),
            trigger="manual_refresh",
        )
    except Exception as exc:
        logger.exception(
            "workspace_feed_refresh_failed workspace_id=%s user_id=%s",
            workspace_id,
            current_user.id,
        )
        generated = {
            "status": "failed",
            "job": {"status": "failed", "error": str(exc) or "Workspace feed refresh failed."},
        }
    try:
        page = get_workspace_feed_page(
            repo=repo,
            workspace_id=workspace_id,
            user_id=int(current_user.id),
            sort=sort,
            limit=limit,
            cursor=cursor,
            include_read=bool(include_read),
        )
    except Exception as exc:
        logger.exception(
            "workspace_feed_refresh_page_failed workspace_id=%s user_id=%s",
            workspace_id,
            current_user.id,
        )
        page = {"items": [], "next_cursor": None, "total_count": 0, "unread_count": 0}
        if not isinstance(generated.get("job"), dict):
            generated["job"] = {}
        generated["job"]["status"] = "failed"
        generated["job"]["error"] = str(exc) or "Workspace feed listing failed."
    return _build_feed_response(
        status=str(generated.get("status") or "unknown"),
        workspace_id=workspace_id,
        page=page,
        job=generated.get("job") if isinstance(generated.get("job"), dict) else None,
    )


@router.post("/{workspace_id}/items/{feed_item_id}/read", response_model=WorkspaceFeedItem)
def set_workspace_feed_item_read(
    workspace_id: int,
    feed_item_id: str,
    payload: WorkspaceFeedReadRequest,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> WorkspaceFeedItem:
    _require_workspace_access(
        repo=repo,
        workspace_id=workspace_id,
        user_id=int(current_user.id),
    )
    row = mark_workspace_feed_item_read(
        repo=repo,
        workspace_id=workspace_id,
        user_id=int(current_user.id),
        feed_item_id=feed_item_id,
        read=bool(payload.read),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Workspace feed item not found.")
    return _map_item(row)
