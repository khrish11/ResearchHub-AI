from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from database import get_db
from models import User, Workspace, Paper, Chat
from routers.auth import get_current_user

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None


class WorkspaceOut(BaseModel):
    id: int
    name: str
    description: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class PaperOut(BaseModel):
    id: int
    title: str
    authors: str
    abstract: str
    url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ChatOut(BaseModel):
    id: int
    message: str
    response: str

    model_config = ConfigDict(from_attributes=True)


class WorkspaceDetail(BaseModel):
    id: int
    name: str
    description: Optional[str]
    papers: List[PaperOut]
    chats: List[ChatOut]

    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=List[WorkspaceOut])
def list_workspaces(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspaces = (
        db.query(Workspace)
        .filter(Workspace.user_id == current_user.id)
        .order_by(Workspace.created_at.desc())
        .all()
    )
    return workspaces


@router.post("/", response_model=WorkspaceOut)
def create_workspace(
    payload: WorkspaceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = Workspace(
        name=payload.name,
        description=payload.description,
        user_id=current_user.id,
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
def get_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id, Workspace.user_id == current_user.id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    papers = db.query(Paper).filter(Paper.workspace_id == workspace.id).all()
    chats = (
        db.query(Chat)
        .filter(Chat.workspace_id == workspace.id)
        .order_by(Chat.timestamp.asc())
        .all()
    )

    return WorkspaceDetail(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        papers=papers,
        chats=chats,
    )


@router.post("/default", response_model=WorkspaceOut)
def get_or_create_default_workspace(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = (
        db.query(Workspace)
        .filter(Workspace.user_id == current_user.id, Workspace.name == "Default Workspace")
        .first()
    )
    if workspace:
        return workspace

    workspace = Workspace(
        name="Default Workspace",
        description="Automatically created workspace for quick imports.",
        user_id=current_user.id,
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


@router.delete("/{workspace_id}")
def delete_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id, Workspace.user_id == current_user.id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Cascade delete papers and chats
    db.query(Paper).filter(Paper.workspace_id == workspace_id).delete()
    db.query(Chat).filter(Chat.workspace_id == workspace_id).delete()
    db.delete(workspace)
    db.commit()
    return {"message": "Workspace deleted successfully"}


@router.get("/{workspace_id}/export")
def export_workspace(
    workspace_id: int,
    format: str = "bibtex",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export papers in a workspace as BibTeX or CSV."""
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id, Workspace.user_id == current_user.id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    papers = db.query(Paper).filter(Paper.workspace_id == workspace.id).all()

    if format not in ("bibtex", "csv"):
        raise HTTPException(status_code=400, detail="Unsupported export format. Use 'bibtex' or 'csv'.")

    # CSV export
    if format == "csv":
        import csv, io
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["title", "authors", "abstract", "url", "published"])
        for p in papers:
            writer.writerow([p.title or "", p.authors or "", p.abstract or "", p.url or "", ""])
        content = buf.getvalue()
        return Response(content=content, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=workspace-{workspace.id}.csv"})

    # BibTeX export
    def _escape(s: str) -> str:
        return (s or "").replace("\n", " ").replace("{", "").replace("}", "").strip()

    entries = []
    for p in papers:
        key = f"paper{p.id}"
        authors = _escape(p.authors)
        title = _escape(p.title)
        year = ""
        url = _escape(p.url)
        abstract = _escape(p.abstract)
        entry = f"@misc{{{key},\n  title = {{{title}}},\n  author = {{{authors}}},\n  year = {{{year}}},\n  url = {{{url}}},\n  abstract = {{{abstract}}}\n}}\n"
        entries.append(entry)
    content = "\n".join(entries)
    return Response(content=content, media_type="application/x-bibtex", headers={"Content-Disposition": f"attachment; filename=workspace-{workspace.id}.bib"})
