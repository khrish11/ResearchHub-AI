from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from repositories import ResearchRepository, get_research_repository
from repositories.research import User
from routers.auth import get_current_user
from services.workspace_insights_service import (
    get_or_generate_workspace_insights,
    get_workspace_insights_job,
)


router = APIRouter(prefix="/workspace-insights", tags=["workspace-insights"])


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
    ws = repo.find_workspace_for_user(int(workspace_id), int(user_id))
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found.")


class WorkspaceInsightItem(BaseModel):
    text: str
    source_refs: List[int] = Field(default_factory=list)


class WorkspaceInsightSource(BaseModel):
    source_index: int
    source_id: str
    source_type: str
    title: str
    similarity_score: float
    url: str = ""
    doi: str = ""


class WorkspaceInsightPayload(BaseModel):
    key_themes: List[WorkspaceInsightItem] = Field(default_factory=list)
    emerging_trends: List[WorkspaceInsightItem] = Field(default_factory=list)
    contradictions: List[WorkspaceInsightItem] = Field(default_factory=list)
    important_findings: List[WorkspaceInsightItem] = Field(default_factory=list)
    research_gaps: List[WorkspaceInsightItem] = Field(default_factory=list)
    recommended_next_steps: List[WorkspaceInsightItem] = Field(default_factory=list)


class WorkspaceInsightsResponse(BaseModel):
    status: str
    workspace_id: int
    insight_id: Optional[str] = None
    confidence: float = 0.0
    disclaimer: str
    generated_at: Optional[str] = None
    expires_at: Optional[str] = None
    sources: List[WorkspaceInsightSource] = Field(default_factory=list)
    payload: WorkspaceInsightPayload = Field(default_factory=WorkspaceInsightPayload)
    job_id: Optional[str] = None
    job_status: Optional[str] = None
    error: Optional[str] = None


class WorkspaceInsightJobStatusResponse(BaseModel):
    job_id: str
    status: str
    workspace_id: int
    user_id: int
    trigger: str
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


def _map_payload(raw_payload: Any) -> WorkspaceInsightPayload:
    payload = raw_payload if isinstance(raw_payload, dict) else {}

    def _items(key: str) -> List[WorkspaceInsightItem]:
        rows = payload.get(key)
        if not isinstance(rows, list):
            return []
        items: List[WorkspaceInsightItem] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            text = str(row.get("text") or "").strip()
            if not text:
                continue
            refs: List[int] = []
            for raw_ref in row.get("source_refs") or []:
                try:
                    ref = int(raw_ref)
                except Exception:
                    continue
                if ref > 0:
                    refs.append(ref)
            items.append(WorkspaceInsightItem(text=text, source_refs=refs))
        return items

    return WorkspaceInsightPayload(
        key_themes=_items("key_themes"),
        emerging_trends=_items("emerging_trends"),
        contradictions=_items("contradictions"),
        important_findings=_items("important_findings"),
        research_gaps=_items("research_gaps"),
        recommended_next_steps=_items("recommended_next_steps"),
    )


def _map_response(
    *,
    status: str,
    workspace_id: int,
    insight: Optional[Dict[str, Any]],
    job: Optional[Dict[str, Any]],
) -> WorkspaceInsightsResponse:
    if not insight:
        return WorkspaceInsightsResponse(
            status=status,
            workspace_id=workspace_id,
            disclaimer=(
                "Insights are AI-generated summaries from workspace evidence and may be incomplete. "
                "Always verify by opening linked sources."
            ),
            payload=WorkspaceInsightPayload(),
            job_id=str(job.get("job_id")) if isinstance(job, dict) and job.get("job_id") else None,
            job_status=str(job.get("status")) if isinstance(job, dict) and job.get("status") else None,
            error=str(job.get("error")) if isinstance(job, dict) and job.get("error") else None,
        )

    raw_sources = insight.get("sources") if isinstance(insight.get("sources"), list) else []
    sources: List[WorkspaceInsightSource] = []
    for row in raw_sources:
        if not isinstance(row, dict):
            continue
        try:
            source_index = int(row.get("source_index") or 0)
        except Exception:
            source_index = 0
        if source_index <= 0:
            continue
        sources.append(
            WorkspaceInsightSource(
                source_index=source_index,
                source_id=str(row.get("source_id") or ""),
                source_type=str(row.get("source_type") or "unknown"),
                title=str(row.get("title") or "Untitled"),
                similarity_score=float(row.get("similarity_score") or 0.0),
                url=str(row.get("url") or ""),
                doi=str(row.get("doi") or ""),
            )
        )
    return WorkspaceInsightsResponse(
        status=status,
        workspace_id=workspace_id,
        insight_id=str(insight.get("insight_id") or "") or None,
        confidence=float(insight.get("confidence") or 0.0),
        disclaimer=str(insight.get("disclaimer") or ""),
        generated_at=_to_iso(insight.get("generated_at")),
        expires_at=_to_iso(insight.get("expires_at")),
        sources=sources,
        payload=_map_payload(insight.get("payload")),
        job_id=str(job.get("job_id")) if isinstance(job, dict) and job.get("job_id") else None,
        job_status=str(job.get("status")) if isinstance(job, dict) and job.get("status") else None,
        error=str(job.get("error")) if isinstance(job, dict) and job.get("error") else None,
    )


@router.get("/jobs/{job_id}", response_model=WorkspaceInsightJobStatusResponse)
def workspace_insights_job_status(
    job_id: str,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> WorkspaceInsightJobStatusResponse:
    row = get_workspace_insights_job(repo=repo, job_id=job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Workspace insights job not found.")
    if int(row.get("user_id") or 0) != int(current_user.id):
        raise HTTPException(status_code=404, detail="Workspace insights job not found.")
    return WorkspaceInsightJobStatusResponse(
        job_id=str(row.get("job_id") or job_id),
        status=str(row.get("status") or "unknown"),
        workspace_id=int(row.get("workspace_id") or 0),
        user_id=int(row.get("user_id") or 0),
        trigger=str(row.get("trigger") or ""),
        error=str(row.get("error") or "") or None,
        result=row.get("result") if isinstance(row.get("result"), dict) else row.get("result"),
        created_at=_to_iso(row.get("created_at")),
        updated_at=_to_iso(row.get("updated_at")),
    )


@router.get("/{workspace_id}", response_model=WorkspaceInsightsResponse)
async def get_workspace_insights(
    workspace_id: int,
    refresh: bool = Query(False),
    run_inline: bool = Query(True),
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> WorkspaceInsightsResponse:
    _require_workspace_access(
        repo=repo,
        workspace_id=workspace_id,
        user_id=int(current_user.id),
    )
    result = await get_or_generate_workspace_insights(
        repo=repo,
        workspace_id=workspace_id,
        user_id=int(current_user.id),
        refresh=bool(refresh),
        run_inline=bool(run_inline),
        trigger="dashboard_open" if not refresh else "manual_refresh",
    )
    return _map_response(
        status=str(result.get("status") or "unknown"),
        workspace_id=workspace_id,
        insight=result.get("insight") if isinstance(result.get("insight"), dict) else None,
        job=result.get("job") if isinstance(result.get("job"), dict) else None,
    )


@router.post("/{workspace_id}/refresh", response_model=WorkspaceInsightsResponse)
async def refresh_workspace_insights(
    workspace_id: int,
    run_inline: bool = Query(True),
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> WorkspaceInsightsResponse:
    _require_workspace_access(
        repo=repo,
        workspace_id=workspace_id,
        user_id=int(current_user.id),
    )
    result = await get_or_generate_workspace_insights(
        repo=repo,
        workspace_id=workspace_id,
        user_id=int(current_user.id),
        refresh=True,
        run_inline=bool(run_inline),
        trigger="manual_refresh",
    )
    return _map_response(
        status=str(result.get("status") or "unknown"),
        workspace_id=workspace_id,
        insight=result.get("insight") if isinstance(result.get("insight"), dict) else None,
        job=result.get("job") if isinstance(result.get("job"), dict) else None,
    )
