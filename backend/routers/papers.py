from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User, Paper, Workspace
from routers.auth import get_current_user
from pydantic import BaseModel
from typing import List, Optional
import httpx
import xml.etree.ElementTree as ET
import re

router = APIRouter(prefix="/papers", tags=["papers"])

ARXIV_API = "https://export.arxiv.org/api/query"

class PaperImport(BaseModel):
    title: str
    authors: List[str]
    abstract: str
    url: Optional[str] = None
    workspace_id: int

def parse_arxiv_feed(xml_text: str) -> list:
    """Parse ArXiv Atom feed into a list of paper dicts."""
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
    }
    root = ET.fromstring(xml_text)
    papers = []
    for entry in root.findall("atom:entry", ns):
        title = (entry.findtext("atom:title", "", ns) or "").strip().replace("\n", " ")
        abstract = (entry.findtext("atom:summary", "", ns) or "").strip().replace("\n", " ")
        authors = [
            a.findtext("atom:name", "", ns)
            for a in entry.findall("atom:author", ns)
        ]
        url = ""
        for link in entry.findall("atom:link", ns):
            if link.get("rel") == "alternate" or link.get("type") == "text/html":
                url = link.get("href", "")
                break
        if not url:
            url = entry.findtext("atom:id", "", ns) or ""

        # Published date
        published = (entry.findtext("atom:published", "", ns) or "")[:10]

        # ArXiv-specific: categories
        categories = [
            cat.get("term", "")
            for cat in entry.findall("atom:category", ns)
        ]

        papers.append({
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "url": url,
            "published": published,
            "categories": categories,
        })
    return papers

@router.get("/search")
async def search_papers(query: str, max_results: int = 10, current_user: User = Depends(get_current_user)):
    """Search ArXiv for real research papers matching the query."""
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(ARXIV_API, params=params)
            response.raise_for_status()
        papers = parse_arxiv_feed(response.text)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"ArXiv API error: {str(e)}")
    except ET.ParseError as e:
        raise HTTPException(status_code=502, detail=f"Failed to parse ArXiv response: {str(e)}")

    return {"papers": papers, "total": len(papers)}

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
