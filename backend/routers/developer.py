import hmac
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database import get_db
from models import Chat, Paper, User, Workspace
from routers.auth import get_current_user, is_developer_email

router = APIRouter(prefix="/developer", tags=["developer"])


def _to_iso(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    return value.isoformat()


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def require_developer_access(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
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


def _user_count_maps(db: Session) -> Dict[str, Dict[int, int]]:
    workspace_counts = {
        int(user_id): int(count)
        for user_id, count in db.query(Workspace.user_id, func.count(Workspace.id)).group_by(Workspace.user_id).all()
        if user_id is not None
    }
    paper_counts = {
        int(user_id): int(count)
        for user_id, count in (
            db.query(Workspace.user_id, func.count(Paper.id))
            .join(Paper, Paper.workspace_id == Workspace.id)
            .group_by(Workspace.user_id)
            .all()
        )
        if user_id is not None
    }
    chat_counts = {
        int(user_id): int(count)
        for user_id, count in (
            db.query(Workspace.user_id, func.count(Chat.id))
            .join(Chat, Chat.workspace_id == Workspace.id)
            .group_by(Workspace.user_id)
            .all()
        )
        if user_id is not None
    }
    return {
        "workspace_counts": workspace_counts,
        "paper_counts": paper_counts,
        "chat_counts": chat_counts,
    }


def _user_row(user: User, counts: Dict[str, Dict[int, int]]) -> Dict[str, Any]:
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
    current_user: User = Depends(require_developer_access),
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_developer_access),
):
    _ = current_user
    counts = _user_count_maps(db)
    recent_users = db.query(User).order_by(User.created_at.desc()).limit(recent_limit).all()
    return {
        "summary": {
            "users": int(db.query(func.count(User.id)).scalar() or 0),
            "workspaces": int(db.query(func.count(Workspace.id)).scalar() or 0),
            "papers": int(db.query(func.count(Paper.id)).scalar() or 0),
            "chats": int(db.query(func.count(Chat.id)).scalar() or 0),
        },
        "recent_users": [_user_row(user, counts) for user in recent_users],
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@router.get("/users")
def developer_users(
    q: Optional[str] = Query(default=None, min_length=1, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_developer_access),
):
    _ = current_user
    query = db.query(User)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(User.email.ilike(like), User.name.ilike(like)))
    total = int(query.count())
    users = query.order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    counts = _user_count_maps(db)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_developer_access),
):
    _ = current_user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    workspaces = (
        db.query(Workspace)
        .filter(Workspace.user_id == user.id)
        .order_by(Workspace.created_at.desc())
        .limit(workspace_limit)
        .all()
    )
    ws_ids = [int(ws.id) for ws in workspaces]

    if ws_ids:
        paper_rows = (
            db.query(Paper.workspace_id, func.count(Paper.id))
            .filter(Paper.workspace_id.in_(ws_ids))
            .group_by(Paper.workspace_id)
            .all()
        )
        chat_rows = (
            db.query(Chat.workspace_id, func.count(Chat.id))
            .filter(Chat.workspace_id.in_(ws_ids))
            .group_by(Chat.workspace_id)
            .all()
        )
    else:
        paper_rows = []
        chat_rows = []

    paper_count_map = {
        int(workspace_id): int(count)
        for workspace_id, count in paper_rows
        if workspace_id is not None
    }
    chat_count_map = {
        int(workspace_id): int(count)
        for workspace_id, count in chat_rows
        if workspace_id is not None
    }

    workspace_payload: List[Dict[str, Any]] = []
    for ws in workspaces:
        papers = (
            db.query(Paper)
            .filter(Paper.workspace_id == ws.id)
            .order_by(Paper.id.desc())
            .limit(papers_per_workspace)
            .all()
        )
        workspace_payload.append(
            {
                "id": int(ws.id),
                "name": ws.name,
                "description": ws.description,
                "created_at": _to_iso(ws.created_at),
                "paper_count": int(paper_count_map.get(int(ws.id), 0)),
                "chat_count": int(chat_count_map.get(int(ws.id), 0)),
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

    counts = _user_count_maps(db)
    return {
        "user": _user_row(user, counts),
        "workspaces": workspace_payload,
    }
