from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from repositories import ResearchRepository, get_research_repository
from routers.auth import get_current_user

router = APIRouter(prefix="/compliance", tags=["compliance"])


AllowedRequestType = Literal[
    "access",
    "delete",
    "rectify",
    "portability",
    "restrict_processing",
    "object_processing",
    "withdraw_consent",
]
AllowedJurisdiction = Literal["gdpr", "ccpa", "other"]


class DataRightsRequestIn(BaseModel):
    request_type: AllowedRequestType
    jurisdiction: AllowedJurisdiction = "other"
    details: str = Field(default="", max_length=6000)


class DataRightsRequestOut(BaseModel):
    id: int
    email: str
    request_type: str
    jurisdiction: Optional[str] = None
    details: Optional[str] = None
    status: str
    submitted_at: Optional[str] = None
    resolved_at: Optional[str] = None


def _as_iso(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _sort_dt(value: Optional[datetime]) -> datetime:
    if not value:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@router.get("/privacy-summary")
async def privacy_summary():
    return {
        "policy_version": "2026-03-04",
        "supports": {
            "gdpr": True,
            "ccpa": True,
            "data_export": True,
            "data_delete": True,
        },
        "retention_defaults": {
            "search_history_days": 365,
            "account_data": "until user deletion request",
        },
    }


@router.post("/data-rights-request", response_model=DataRightsRequestOut)
async def create_data_rights_request(
    payload: DataRightsRequestIn,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: Any = Depends(get_current_user),
):
    row = repo.create_data_rights_request(
        user_id=current_user.id,
        email=str(current_user.email or "").strip().lower(),
        request_type=str(payload.request_type),
        jurisdiction=str(payload.jurisdiction),
        details=str(payload.details or "").strip()[:6000],
        status="submitted",
    )
    return DataRightsRequestOut(
        id=row.id,
        email=row.email,
        request_type=row.request_type,
        jurisdiction=row.jurisdiction,
        details=row.details,
        status=row.status,
        submitted_at=_as_iso(row.submitted_at),
        resolved_at=_as_iso(row.resolved_at),
    )


@router.get("/data-rights-request/me")
async def list_my_data_rights_requests(
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: Any = Depends(get_current_user),
):
    rows = repo.list_data_rights_requests_for_user(current_user.id, limit=100)
    items = [
        DataRightsRequestOut(
            id=row.id,
            email=row.email,
            request_type=row.request_type,
            jurisdiction=row.jurisdiction,
            details=row.details,
            status=row.status,
            submitted_at=_as_iso(row.submitted_at),
            resolved_at=_as_iso(row.resolved_at),
        ).model_dump()
        for row in rows
    ]
    return {"items": items, "count": len(items)}


def _workspace_payload(workspace: Any) -> Dict[str, Any]:
    return {
        "id": workspace.id,
        "name": workspace.name,
        "description": workspace.description,
        "created_at": _as_iso(workspace.created_at),
    }


def _paper_payload(paper: Any) -> Dict[str, Any]:
    return {
        "id": paper.id,
        "workspace_id": paper.workspace_id,
        "title": paper.title,
        "authors": paper.authors,
        "abstract": paper.abstract,
        "url": paper.url,
        "doi": paper.doi,
        "source": paper.source,
        "pdf_url": paper.pdf_url,
        "access_type": paper.access_type,
        "full_text_available": bool(paper.full_text_available),
    }


def _chat_payload(chat: Any) -> Dict[str, Any]:
    return {
        "id": chat.id,
        "workspace_id": chat.workspace_id,
        "message": chat.message,
        "response": chat.response,
        "timestamp": _as_iso(chat.timestamp),
    }


def _search_payload(row: Any) -> Dict[str, Any]:
    return {
        "id": row.id,
        "query": row.query,
        "source": row.source,
        "result_count": row.result_count,
        "filters_json": row.filters_json,
        "created_at": _as_iso(row.created_at),
    }


def _document_payload(row: Any) -> Dict[str, Any]:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "title": row.title,
        "content": row.content,
        "version": row.version,
        "created_at": _as_iso(row.created_at),
        "updated_at": _as_iso(row.updated_at),
    }


def _workspace_file_payload(row: Any) -> Dict[str, Any]:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "paper_id": row.paper_id,
        "kind": row.kind,
        "filename": row.filename,
        "storage_bucket": row.storage_bucket,
        "storage_path": row.storage_path,
        "content_type": row.content_type,
        "size_bytes": int(row.size_bytes or 0),
        "download_url": row.download_url,
        "created_at": _as_iso(row.created_at),
    }


@router.get("/export-my-data")
async def export_my_data(
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: Any = Depends(get_current_user),
):
    workspaces = sorted(
        repo.list_workspaces_for_user(current_user.id),
        key=lambda row: _sort_dt(row.created_at),
    )
    workspace_ids = [w.id for w in workspaces]

    papers: List[Any] = []
    chats: List[Any] = []
    workspace_files: List[Any] = []
    if workspace_ids:
        for workspace in workspaces:
            papers.extend(repo.list_papers_for_workspace(workspace.id))
            chats.extend(repo.list_chats_for_workspace(workspace.id, ascending=True))
            workspace_files.extend(repo.list_workspace_files_for_workspace(workspace.id, current_user.id))

    papers.sort(key=lambda row: int(row.id))
    chats.sort(key=lambda row: int(row.id))
    search_rows = repo.list_search_history_for_user(current_user.id, limit=1000)
    docs = repo.list_workspace_documents_for_user(current_user.id)
    dsr_rows = repo.list_data_rights_requests_for_user(current_user.id)

    return {
        "exported_at": _as_iso(datetime.now(timezone.utc)),
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "is_verified": bool(current_user.is_verified),
            "created_at": _as_iso(current_user.created_at),
        },
        "workspaces": [_workspace_payload(w) for w in workspaces],
        "papers": [_paper_payload(p) for p in papers],
        "chats": [_chat_payload(c) for c in chats],
        "search_history": [_search_payload(s) for s in search_rows],
        "documents": [_document_payload(d) for d in docs],
        "workspace_files": [_workspace_file_payload(row) for row in workspace_files],
        "data_rights_requests": [
            {
                "id": row.id,
                "email": row.email,
                "request_type": row.request_type,
                "jurisdiction": row.jurisdiction,
                "details": row.details,
                "status": row.status,
                "submitted_at": _as_iso(row.submitted_at),
                "resolved_at": _as_iso(row.resolved_at),
            }
            for row in dsr_rows
        ],
    }
