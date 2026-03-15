import hmac
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from repositories import ResearchRepository, get_research_repository
from routers.auth import get_current_user, is_developer_email

router = APIRouter(prefix="/developer", tags=["developer"])


def _to_iso(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _sort_dt(value: Optional[datetime]) -> datetime:
    if not value:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def require_developer_access(
    request: Request,
    current_user: Any = Depends(get_current_user),
) -> Any:
    if is_developer_email(current_user.email):
        return current_user

    configured_key = (os.getenv("DEV_ACCESS_KEY") or "").strip()
    header_key = (request.headers.get("x-dev-key") or "").strip()
    if configured_key and header_key and hmac.compare_digest(configured_key, header_key):
        return current_user

    app_env = (os.getenv("APP_ENV") or "production").strip().lower()
    allow_local = _is_truthy(os.getenv("ALLOW_DEV_PANEL", "1" if app_env == "development" else "0"))
    if allow_local and app_env == "development":
        return current_user

    raise HTTPException(
        status_code=403,
        detail=(
            "Developer access denied. Add your email to DEVELOPER_EMAILS or use "
            "header X-Dev-Key with DEV_ACCESS_KEY."
        ),
    )


def _user_count_maps(repo: ResearchRepository) -> Dict[str, Dict[int, int]]:
    workspace_counts: Dict[int, int] = {}
    paper_counts: Dict[int, int] = {}
    chat_counts: Dict[int, int] = {}
    for user in repo.list_users():
        workspaces = repo.list_workspaces_for_user(user.id)
        workspace_counts[int(user.id)] = len(workspaces)
        paper_total = 0
        chat_total = 0
        for workspace in workspaces:
            paper_total += len(repo.list_papers_for_workspace(workspace.id))
            chat_total += len(repo.list_chats_for_workspace(workspace.id))
        paper_counts[int(user.id)] = paper_total
        chat_counts[int(user.id)] = chat_total
    return {
        "workspace_counts": workspace_counts,
        "paper_counts": paper_counts,
        "chat_counts": chat_counts,
    }


def _user_row(user: Any, counts: Dict[str, Dict[int, int]]) -> Dict[str, Any]:
    return {
        "id": int(user.id),
        "email": user.email,
        "name": user.name,
        "is_active": bool(user.is_active),
        "is_verified": bool(user.is_verified),
        "created_at": _to_iso(user.created_at),
        "updated_at": _to_iso(user.updated_at),
        "workspace_count": int(counts["workspace_counts"].get(int(user.id), 0)),
        "paper_count": int(counts["paper_counts"].get(int(user.id), 0)),
        "chat_count": int(counts["chat_counts"].get(int(user.id), 0)),
    }


@router.get("/access")
def developer_access_status(
    request: Request,
    current_user: Any = Depends(require_developer_access),
):
    _ = request
    return {
        "ok": True,
        "user_id": current_user.id,
        "email": current_user.email,
        "mode": "developer_email" if is_developer_email(current_user.email) else "header_or_dev_env",
    }


@router.get("/overview")
def developer_overview(
    recent_limit: int = Query(default=20, ge=1, le=100),
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: Any = Depends(require_developer_access),
):
    _ = current_user
    counts = _user_count_maps(repo)
    recent_users = repo.list_users(limit=recent_limit)
    return {
        "summary": {
            "users": int(repo.count_users()),
            "workspaces": int(repo.count_workspaces()),
            "papers": int(repo.count_papers()),
            "chats": int(repo.count_chats()),
        },
        "recent_users": [_user_row(user, counts) for user in recent_users],
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@router.get("/users")
def developer_users(
    q: Optional[str] = Query(default=None, min_length=1, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: Any = Depends(require_developer_access),
):
    _ = current_user
    total = len(repo.list_users(query=q))
    users = repo.list_users(query=q, limit=limit, offset=offset)
    counts = _user_count_maps(repo)
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "users": [_user_row(user, counts) for user in users],
    }


@router.get("/users/{user_id}")
def developer_user_detail(
    user_id: int,
    workspace_limit: int = Query(default=20, ge=1, le=100),
    papers_per_workspace: int = Query(default=10, ge=1, le=50),
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: Any = Depends(require_developer_access),
):
    _ = current_user
    user = repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    workspaces = sorted(
        repo.list_workspaces_for_user(user.id),
        key=lambda row: _sort_dt(row.created_at),
        reverse=True,
    )[:workspace_limit]

    workspace_payload: List[Dict[str, Any]] = []
    for ws in workspaces:
        papers = sorted(repo.list_papers_for_workspace(ws.id), key=lambda paper: int(paper.id), reverse=True)[
            :papers_per_workspace
        ]
        chat_count = len(repo.list_chats_for_workspace(ws.id))
        workspace_payload.append(
            {
                "id": int(ws.id),
                "name": ws.name,
                "description": ws.description,
                "created_at": _to_iso(ws.created_at),
                "paper_count": len(repo.list_papers_for_workspace(ws.id)),
                "chat_count": chat_count,
                "papers": [
                    {
                        "id": int(paper.id),
                        "title": paper.title,
                        "authors": paper.authors,
                        "doi": paper.doi,
                        "url": paper.url,
                    }
                    for paper in papers
                ],
            }
        )

    counts = _user_count_maps(repo)
    return {
        "user": _user_row(user, counts),
        "workspaces": workspace_payload,
    }
