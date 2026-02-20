from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User, Paper, Workspace
from routers.auth import get_current_user
from pydantic import BaseModel
from typing import List, Optional
import httpx
import xml.etree.ElementTree as ET

import os

router = APIRouter(prefix="/papers", tags=["papers"])

ARXIV_API = "https://export.arxiv.org/api/query"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
IEEE_XPLORE_API = "https://ieeexploreapi.ieee.org/api/v1/search/articles"
IEEE_API_KEY = os.getenv("IEEE_XPLORE_API_KEY", "")

SPRINGER_META_API = "https://api.springernature.com/meta/v2/json"
SPRINGER_KEY = os.getenv("SPRINGER_META_KEY") or os.getenv("SPRINGER_OPEN_ACCESS_KEY", "")

NASA_ADS_API = "https://api.adsabs.harvard.edu/v1/search/query"
NASA_ADS_TOKEN = os.getenv("NASA_ADS_TOKEN", "")

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class PaperImport(BaseModel):
    title: str
    authors: List[str]
    abstract: str
    url: Optional[str] = None
    workspace_id: int


# ---------------------------------------------------------------------------
# ArXiv helpers
# ---------------------------------------------------------------------------

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
        authors = [a.findtext("atom:name", "", ns) for a in entry.findall("atom:author", ns)]
        url = ""
        for link in entry.findall("atom:link", ns):
            if link.get("rel") == "alternate" or link.get("type") == "text/html":
                url = link.get("href", "")
                break
        if not url:
            url = entry.findtext("atom:id", "", ns) or ""
        published = (entry.findtext("atom:published", "", ns) or "")[:10]
        categories = [cat.get("term", "") for cat in entry.findall("atom:category", ns)]
        papers.append({
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "url": url,
            "published": published,
            "categories": categories,
            "source": "arxiv",
        })
    return papers


# ---------------------------------------------------------------------------
# ArXiv search
# ---------------------------------------------------------------------------

@router.get("/search")
async def search_papers(
    query: str,
    max_results: int = 15,
    category: Optional[str] = None,
    sort_by: Optional[str] = "relevance",
    current_user: User = Depends(get_current_user),
):
    """Search ArXiv for research papers with optional category + sort filters."""
    if category and category != "all":
        search_query = f"cat:{category} AND all:{query}"
    else:
        search_query = f"all:{query}"

    valid_sorts = {"relevance", "lastUpdatedDate", "submittedDate"}
    sort = sort_by if sort_by in valid_sorts else "relevance"

    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": sort,
        "sortOrder": "descending",
    }

    # Retry up to 2 times with increasing timeout
    last_error = None
    for timeout_secs in (20, 35):
        try:
            async with httpx.AsyncClient(timeout=timeout_secs) as client:
                response = await client.get(ARXIV_API, params=params)
                response.raise_for_status()
            papers = parse_arxiv_feed(response.text)
            return {"papers": papers, "total": len(papers), "source": "arxiv"}
        except httpx.TimeoutException as e:
            last_error = f"ArXiv timed out ({timeout_secs}s). Try again or switch to Semantic Scholar."
            continue
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"ArXiv API error: {str(e)}")
        except ET.ParseError as e:
            raise HTTPException(status_code=502, detail=f"Failed to parse ArXiv response: {str(e)}")

    raise HTTPException(status_code=504, detail=last_error)


# ---------------------------------------------------------------------------
# Semantic Scholar search  (200M+ papers, all disciplines, free — no key)
# ---------------------------------------------------------------------------

@router.get("/search-semantic")
async def search_semantic(
    query: str,
    max_results: int = 15,
    current_user: User = Depends(get_current_user),
):
    """Search Semantic Scholar — 200M+ papers across all disciplines. No API key needed."""
    params = {
        "query": query,
        "limit": min(max_results, 100),
        "fields": "title,authors,abstract,year,externalIds,publicationTypes,openAccessPdf,url",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                SEMANTIC_SCHOLAR_API,
                params=params,
                headers={"User-Agent": "ResearchHub-AI/1.0"},
            )
            response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Semantic Scholar timed out. Please try again.")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Semantic Scholar API error: {str(e)}")

    papers = []
    for item in data.get("data", []):
        authors = [a.get("name", "") for a in (item.get("authors") or [])]
        abstract = item.get("abstract") or "No abstract available."
        year = item.get("year")
        published = str(year) if year else ""

        # Prefer open-access PDF url, fallback to semanticscholar url
        url = ""
        if item.get("openAccessPdf"):
            url = item["openAccessPdf"].get("url", "")
        external = item.get("externalIds") or {}
        doi = external.get("DOI")
        if not url:
            if doi:
                url = f"https://doi.org/{doi}"
        if not url:
            url = item.get("url") or ""

        # Derive simple category tags from publicationTypes
        categories = item.get("publicationTypes") or []

        papers.append({
            "title": item.get("title") or "",
            "authors": authors,
            "abstract": abstract,
            "url": url,
            "published": published,
            "categories": categories,
            "doi": doi or "",
            "source": "semantic_scholar",
        })

    return {"papers": papers, "total": len(papers), "source": "semantic_scholar"}


# ---------------------------------------------------------------------------
# IEEE Xplore search  (200/day free tier, needs API key)
# ---------------------------------------------------------------------------

@router.get("/search-ieee")
async def search_ieee(
    query: str,
    max_results: int = 15,
    current_user: User = Depends(get_current_user),
):
    """Search IEEE Xplore — engineering, electronics, CS papers. Requires IEEE_XPLORE_API_KEY."""
    if not IEEE_API_KEY:
        raise HTTPException(status_code=503, detail="IEEE Xplore API key not configured. Add IEEE_XPLORE_API_KEY to .env")

    params = {
        "querytext": query,
        "max_records": min(max_results, 25),
        "start_record": 1,
        "sort_order": "desc",
        "sort_field": "relevance",
        "apikey": IEEE_API_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                IEEE_XPLORE_API,
                params=params,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="IEEE Xplore timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise HTTPException(status_code=401, detail="IEEE Xplore API key invalid or not yet activated. Wait a few minutes after registration.")
        raise HTTPException(status_code=502, detail=f"IEEE Xplore API error: {str(e)}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"IEEE Xplore API error: {str(e)}")

    papers = []
    for item in data.get("articles", []):
        # Authors
        authors_data = (item.get("authors") or {}).get("authors") or []
        authors = [a.get("full_name", "") for a in authors_data]

        abstract = item.get("abstract") or "No abstract available."
        year = item.get("publication_year") or item.get("conference_dates") or ""
        published = str(year)

        url = item.get("html_url") or item.get("pdf_url") or ""
        doi = item.get("doi")
        if doi and not url:
            url = f"https://doi.org/{doi}"

        content_type = item.get("content_type") or ""
        publication_title = item.get("publication_title") or ""
        categories = [c for c in [content_type, publication_title] if c]

        papers.append({
            "title": item.get("title") or "",
            "authors": authors,
            "abstract": abstract,
            "url": url,
            "published": published,
            "categories": categories[:3],
            "doi": doi or "",
            "publication_title": publication_title or "",
            "source": "ieee",
        })

    return {"papers": papers, "total": len(papers), "source": "ieee"}


# ---------------------------------------------------------------------------
# Springer Nature search  (Meta API — broad science/engineering coverage)
# ---------------------------------------------------------------------------

@router.get("/search-springer")
async def search_springer(
    query: str,
    max_results: int = 15,
    current_user: User = Depends(get_current_user),
):
    """Search Springer Nature Meta API (~12M articles, science & engineering)."""
    if not SPRINGER_KEY:
        raise HTTPException(status_code=503, detail="Springer Nature API key not configured.")

    params = {
        "q": query,
        "p": min(max_results, 25),
        "api_key": SPRINGER_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(SPRINGER_META_API, params=params)
            response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Springer API timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="Springer API key invalid.")
        raise HTTPException(status_code=502, detail=f"Springer API error: {str(e)}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Springer API error: {str(e)}")

    papers = []
    for item in data.get("records", []):
        creators = item.get("creators") or []
        authors = [c.get("creator", "") for c in creators]

        abstract = item.get("abstract") or "No abstract available."
        published = (item.get("publicationDate") or item.get("onlineDate") or "")[:10]

        # URL — prefer DOI
        doi = item.get("doi") or ""
        url = f"https://doi.org/{doi}" if doi else (item.get("url") or [{}])[0].get("value", "")

        subjects = [s.get("term", "") for s in (item.get("subjects") or [])]
        pub_name = item.get("publicationName") or ""
        categories = ([pub_name] if pub_name else []) + subjects[:2]

        papers.append({
            "title": item.get("title") or "",
            "authors": authors,
            "abstract": abstract,
            "url": url,
            "published": published,
            "categories": categories[:3],
            "doi": doi or "",
            "source": "springer",
        })

    return {"papers": papers, "total": len(papers), "source": "springer"}


# ---------------------------------------------------------------------------
# NASA ADS search  (astrophysics, astronomy, physics, geoscience)
# ---------------------------------------------------------------------------

@router.get("/search-nasa")
async def search_nasa_ads(
    query: str,
    max_results: int = 15,
    current_user: User = Depends(get_current_user),
):
    """Search NASA Astrophysics Data System — 15M+ astrophysics and physics papers."""
    if not NASA_ADS_TOKEN:
        raise HTTPException(status_code=503, detail="NASA ADS token not configured.")

    params = {
        "q": query,
        "fl": "title,author,abstract,year,doi,bibcode,doctype",
        "rows": min(max_results, 50),
        "sort": "score desc",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                NASA_ADS_API,
                params=params,
                headers={"Authorization": f"Bearer {NASA_ADS_TOKEN}"},
            )
            response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="NASA ADS timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="NASA ADS token invalid.")
        raise HTTPException(status_code=502, detail=f"NASA ADS error: {str(e)}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"NASA ADS error: {str(e)}")

    docs = (data.get("response") or {}).get("docs") or []
    papers = []
    for item in docs:
        raw_title = item.get("title") or [""]
        title = raw_title[0] if isinstance(raw_title, list) else raw_title

        authors = item.get("author") or []
        abstract = item.get("abstract") or "No abstract available."
        year = item.get("year") or ""
        published = str(year)

        doi_list = item.get("doi") or []
        doi = doi_list[0] if doi_list else ""
        url = f"https://doi.org/{doi}" if doi else f"https://ui.adsabs.harvard.edu/abs/{item.get('bibcode', '')}"

        doctype = item.get("doctype") or ""
        categories = [doctype] if doctype else []

        papers.append({
            "title": title,
            "authors": authors[:8],
            "abstract": abstract,
            "url": url,
            "published": published,
            "categories": categories,
            "doi": doi or "",
            "bibcode": item.get('bibcode', '') or "",
            "source": "nasa_ads",
        })

    return {"papers": papers, "total": len(papers), "source": "nasa_ads"}


# ---------------------------------------------------------------------------
# Import a paper into a workspace
# ---------------------------------------------------------------------------

@router.post("/import")
async def import_paper(
    paper_data: PaperImport,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == paper_data.workspace_id, Workspace.user_id == current_user.id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    new_paper = Paper(
        title=paper_data.title,
        authors=", ".join(paper_data.authors),
        abstract=paper_data.abstract,
        url=paper_data.url,
        workspace_id=paper_data.workspace_id,
    )
    db.add(new_paper)
    db.commit()
    db.refresh(new_paper)
    return {"message": "Paper imported successfully", "paper_id": new_paper.id}
