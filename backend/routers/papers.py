from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User, Paper, Workspace
from routers.auth import get_current_user
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/papers", tags=["papers"])

class PaperImport(BaseModel):
    title: str
    authors: List[str]
    abstract: str
    url: Optional[str] = None
    workspace_id: int

class SearchQuery(BaseModel):
    query: str

@router.get("/search")
async def search_papers(query: str, current_user: User = Depends(get_current_user)):
    # Mock search for now as we don't have real API keys for ArXiv/PubMed in env yet
    # In a real app, use `arxiv` python package or similar
    mock_results = [
        {
            "title": f"Research on {query} - Paper 1",
            "authors": ["Author A", "Author B"],
            "abstract": f"This is a mock abstract for {query}. It discusses interesting findings.",
            "url": "http://arxiv.org/abs/1234.5678"
        },
        {
            "title": f"Advanced {query} Techniques",
            "authors": ["Author C"],
            "abstract": f"Another abstract about {query}. Very insightful.",
            "url": "http://arxiv.org/abs/5678.1234"
        }
    ]
    return {"papers": mock_results}

@router.post("/import")
async def import_paper(paper_data: PaperImport, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Verify workspace belongs to user
    workspace = db.query(Workspace).filter(Workspace.id == paper_data.workspace_id, Workspace.user_id == current_user.id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    new_paper = Paper(
        title=paper_data.title,
        authors=", ".join(paper_data.authors),
        abstract=paper_data.abstract,
        url=paper_data.url,
        workspace_id=paper_data.workspace_id
    )
    db.add(new_paper)
    db.commit()
    db.refresh(new_paper)
    return {"message": "Paper imported successfully", "paper_id": new_paper.id}
