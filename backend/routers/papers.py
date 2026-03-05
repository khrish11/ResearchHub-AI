from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal, get_db
from models import SearchHistory, User, Paper, Workspace
from routers.auth import get_current_user
from pydantic import BaseModel, Field
from typing import List, Optional, Tuple
import asyncio
import httpx
import xml.etree.ElementTree as ET

import os
import logging
import re
from pathlib import Path
from dotenv import dotenv_values
from typing import Dict, Any
from datetime import datetime, timezone
from urllib.parse import quote
from datetime import date, timedelta
import time
from copy import deepcopy
import json

router = APIRouter(prefix="/papers", tags=["papers"])

# Simple in-memory cache for global search responses (process-local).
GLOBAL_SEARCH_CACHE_TTL_SECONDS = 300
GLOBAL_SEARCH_CACHE_MAX_ITEMS = 200
_GLOBAL_SEARCH_CACHE: Dict[str, Dict[str, Any]] = {}
_GLOBAL_SEARCH_METRICS: Dict[str, Any] = {
    "requests_total": 0,
    "cache_hits_total": 0,
    "partial_results_total": 0,
    "errors_total": 0,
    "timeouts_total": 0,
    "last_duration_ms": 0,
    "last_cached": False,
    "last_source_status": {},
    "last_checked_at": None,
}
# Keep multi-source search responsive: each source has a bounded budget and
# the whole request returns partial merged results quickly.
GLOBAL_SOURCE_TIMEOUT_SECONDS = 6.0
GLOBAL_SEARCH_WAIT_SECONDS = 8.0
GLOBAL_SOURCE_CONCURRENCY = 7
GLOBAL_UNPAYWALL_TIMEOUT_SECONDS = 2.0
GLOBAL_UNPAYWALL_MAX_LOOKUPS = 2
GLOBAL_UNPAYWALL_MAX_LOOKUPS_BY_MODE: Dict[str, int] = {
    "fast": 0,
    "balanced": GLOBAL_UNPAYWALL_MAX_LOOKUPS,
    "deep": 4,
}
GLOBAL_SOURCE_TIMEOUT_OVERRIDES: Dict[str, float] = {
    "openalex": 5.0,
    "arxiv": 5.0,
    "semantic": 5.0,
    "crossref": 5.5,
    "dblp": 4.5,
    "zenodo": 4.5,
    "openaire": 5.0,
    "figshare": 4.5,
    "osf": 4.5,
    "dryad": 4.5,
    "inspire": 4.5,
    "springer": 5.0,
    "europepmc": 5.0,
    "doaj": 5.0,
    "hal": 5.0,
    "plos": 4.5,
    "pubmed": 5.5,
    "nasa": 5.0,
    "elife": 5.0,
    "datacite": 4.5,
    "biorxiv": 4.5,
    "medrxiv": 4.5,
}

GLOBAL_SEARCH_SOURCE_PRESETS: Dict[str, List[str]] = {
    "fast": [
        "openalex",
        "arxiv",
        "semantic",
        "inspire",
        "dblp",
        "openaire",
        "osf",
        "europepmc",
        "pubmed",
        "biorxiv",
        "medrxiv",
        "doaj",
    ],
    "balanced": [
        "openalex",
        "arxiv",
        "europepmc",
        "pubmed",
        "doaj",
        "hal",
        "biorxiv",
        "medrxiv",
        "plos",
        "elife",
        "openaire",
        "figshare",
        "osf",
        "dryad",
        "inspire",
        "dblp",
        "zenodo",
        "semantic",
        "springer",
        "datacite",
        "nasa",
    ],
    "deep": [
        "openalex",
        "arxiv",
        "europepmc",
        "pubmed",
        "doaj",
        "hal",
        "biorxiv",
        "medrxiv",
        "plos",
        "elife",
        "openaire",
        "figshare",
        "osf",
        "dryad",
        "inspire",
        "dblp",
        "zenodo",
        "semantic",
        "springer",
        "datacite",
        "crossref",
        "nasa",
    ],
}

GLOBAL_SEARCH_MAX_RESULTS_BY_MODE: Dict[str, int] = {
    "fast": 100,
    "balanced": 140,
    "deep": 200,
}

GLOBAL_SOURCE_CONCURRENCY_BY_MODE: Dict[str, int] = {
    "fast": 6,
    "balanced": GLOBAL_SOURCE_CONCURRENCY,
    "deep": 9,
}

GLOBAL_SEARCH_WAIT_BY_MODE: Dict[str, float] = {
    "fast": 5.5,
    "balanced": GLOBAL_SEARCH_WAIT_SECONDS,
    "deep": 11.0,
}

GLOBAL_SOURCE_TIMEOUT_FACTOR_BY_MODE: Dict[str, float] = {
    "fast": 0.7,
    "balanced": 1.0,
    "deep": 1.15,
}

ARXIV_API = "https://export.arxiv.org/api/query"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
OPENALEX_API = "https://api.openalex.org/works"
EUROPE_PMC_API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
CROSSREF_API = "https://api.crossref.org/works"
PUBMED_ESEARCH_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
DOAJ_API_BASE = "https://doaj.org/api/search/articles"
DATACITE_WORKS_API = "https://api.datacite.org/works"
DBLP_API = "https://dblp.org/search/publ/api"
ZENODO_API = "https://zenodo.org/api/records"
OPENAIRE_API = "https://api.openaire.eu/search/publications"
FIGSHARE_API = "https://api.figshare.com/v2/articles"
OSF_PREPRINT_API = "https://api.osf.io/v2/preprints/"
DRYAD_API = "https://datadryad.org/api/v2/search"
INSPIRE_HEP_API = "https://inspirehep.net/api/literature"
UNPAYWALL_API = "https://api.unpaywall.org/v2/"
HAL_API_SEARCH = "https://api.archives-ouvertes.fr/search/"
BIORXIV_API_BASE = "https://api.biorxiv.org/details"
PLOS_API = "https://api.plos.org/search"

SPRINGER_META_API = "https://api.springernature.com/meta/v2/json"

NASA_ADS_API = "https://api.adsabs.harvard.edu/v1/search/query"

OPEN_ACCESS_SOURCES = {
    "arxiv",
    "europepmc",
    "europe_pmc",
    "doaj",
    "hal",
    "biorxiv",
    "medrxiv",
    "plos",
    "elife",
    "pubmed",
    "openalex",
    "zenodo",
    "openaire",
    "figshare",
    "osf",
    "dryad",
}

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class PaperImport(BaseModel):
    title: str
    authors: List[str]
    abstract: str
    url: Optional[str] = None
    doi: Optional[str] = None
    bibcode: Optional[str] = None
    source: Optional[str] = None
    pdf_url: Optional[str] = None
    institutional_url: Optional[str] = None
    access_type: Optional[str] = None
    full_text_available: Optional[bool] = None
    workspace_id: int


class InstitutionalPaperEntry(BaseModel):
    title: str = Field(min_length=2, max_length=600)
    url: Optional[str] = Field(default=None, max_length=2000)
    doi: Optional[str] = Field(default=None, max_length=300)
    authors: Optional[List[str]] = None
    abstract: Optional[str] = Field(default="", max_length=6000)
    pdf_url: Optional[str] = Field(default=None, max_length=2000)
    institutional_url: Optional[str] = Field(default=None, max_length=2000)


class InstitutionalImportRequest(BaseModel):
    workspace_id: int
    source_name: str = Field(default="institutional_portal", max_length=120)
    entries: Optional[List[InstitutionalPaperEntry]] = None
    raw_text: Optional[str] = Field(default=None, max_length=150000)


class AccessResolveRequest(BaseModel):
    workspace_id: Optional[int] = None
    paper_id: Optional[int] = None
    title: Optional[str] = Field(default="", max_length=600)
    source: Optional[str] = Field(default="", max_length=120)
    doi: Optional[str] = Field(default=None, max_length=300)
    url: Optional[str] = Field(default=None, max_length=2000)
    pdf_url: Optional[str] = Field(default=None, max_length=2000)
    institutional_url: Optional[str] = Field(default=None, max_length=2000)


class WorkspaceAccessResolveRequest(BaseModel):
    workspace_id: int
    refresh_all: bool = False
    max_unpaywall_lookups: int = Field(default=20, ge=2, le=80)


def _record_search_history(
    user_id: int,
    query: str,
    result_count: int,
    max_results: int,
    offset: int,
    source_status: Optional[Dict[str, Any]] = None,
    cache_hit: bool = False,
) -> None:
    trimmed_query = (query or "").strip()
    if not trimmed_query:
        return

    payload = {
        "max_results": max(1, int(max_results or 0)),
        "offset": max(0, int(offset or 0)),
        "cache_hit": bool(cache_hit),
        "source_status": source_status or {},
    }

    db = SessionLocal()
    try:
        latest = (
            db.query(SearchHistory)
            .filter(SearchHistory.user_id == user_id, SearchHistory.source == "global_merged")
            .order_by(SearchHistory.created_at.desc())
            .first()
        )
        now_utc = datetime.now(timezone.utc)
        should_update_latest = False
        if latest and str(latest.query or "").strip().lower() == trimmed_query.lower():
            created = latest.created_at
            if created is not None:
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                age_seconds = abs((now_utc - created).total_seconds())
                should_update_latest = age_seconds <= 240

        if should_update_latest and latest is not None:
            latest.result_count = max(0, int(result_count or 0))
            latest.filters_json = json.dumps(payload)
            latest.created_at = now_utc
        else:
            db.add(
                SearchHistory(
                    user_id=user_id,
                    query=trimmed_query[:300],
                    source="global_merged",
                    result_count=max(0, int(result_count or 0)),
                    filters_json=json.dumps(payload),
                    created_at=now_utc,
                )
            )
        db.commit()

        old_rows = (
            db.query(SearchHistory.id)
            .filter(SearchHistory.user_id == user_id)
            .order_by(SearchHistory.created_at.desc())
            .offset(250)
            .all()
        )
        old_ids = [int(row[0]) for row in old_rows]
        if old_ids:
            db.query(SearchHistory).filter(SearchHistory.id.in_(old_ids)).delete(synchronize_session=False)
            db.commit()
    except Exception:
        logging.exception("Failed to record search history")
        db.rollback()
    finally:
        db.close()


def _get_nasa_token() -> str:
    """Resolve NASA token from process env, then backend/.env fallback."""
    token = (os.getenv("NASA_ADS_TOKEN") or "").strip()
    if token:
        return token
    env_path = Path(__file__).resolve().parents[1] / '.env'
    vals = dotenv_values(env_path)
    token = (vals.get('NASA_ADS_TOKEN') or '').strip()
    if token:
        os.environ['NASA_ADS_TOKEN'] = token
    return token


def _get_springer_key() -> str:
    """Resolve Springer key from process env, then backend/.env fallback."""
    key = (os.getenv("SPRINGER_META_KEY") or os.getenv("SPRINGER_OPEN_ACCESS_KEY") or "").strip()
    if key:
        return key
    env_path = Path(__file__).resolve().parents[1] / '.env'
    vals = dotenv_values(env_path)
    key = (vals.get('SPRINGER_META_KEY') or vals.get('SPRINGER_OPEN_ACCESS_KEY') or '').strip()
    if key:
        if not os.getenv("SPRINGER_META_KEY"):
            os.environ["SPRINGER_META_KEY"] = key
    return key


def _get_groq_key() -> str:
    """Resolve Groq key from process env, then backend/.env fallback."""
    key = (os.getenv("GROQ_API_KEY") or "").strip()
    if key:
        return key
    env_path = Path(__file__).resolve().parents[1] / '.env'
    vals = dotenv_values(env_path)
    key = (vals.get('GROQ_API_KEY') or '').strip()
    if key:
        os.environ['GROQ_API_KEY'] = key
    return key


def _get_semantic_key() -> str:
    """Resolve Semantic Scholar key from env, then backend/.env fallback."""
    key = (os.getenv("SEMANTIC_SCHOLAR_API_KEY") or "").strip()
    if key:
        return key
    env_path = Path(__file__).resolve().parents[1] / '.env'
    vals = dotenv_values(env_path)
    key = (vals.get('SEMANTIC_SCHOLAR_API_KEY') or '').strip()
    if key:
        os.environ['SEMANTIC_SCHOLAR_API_KEY'] = key
    return key


def _decode_openalex_abstract(abstract_index: Any) -> str:
    """Rebuild OpenAlex abstract text from abstract_inverted_index."""
    if not isinstance(abstract_index, dict):
        return "No abstract available."

    positioned_tokens: List[Tuple[int, str]] = []
    for token, positions in abstract_index.items():
        if not isinstance(positions, list):
            continue
        for pos in positions:
            if isinstance(pos, int):
                positioned_tokens.append((pos, token))

    if not positioned_tokens:
        return "No abstract available."

    positioned_tokens.sort(key=lambda x: x[0])
    return " ".join(token for _, token in positioned_tokens).strip() or "No abstract available."


def _normalize_title(title: str) -> str:
    """Normalize title for cross-source de-duplication."""
    text = (title or "").lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _paper_dedupe_key(paper: Dict[str, Any]) -> str:
    """Prefer DOI, then bibcode, then normalized title."""
    doi = str(paper.get("doi") or "").lower().strip()
    if doi:
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
        return f"doi:{doi}"

    bibcode = str(paper.get("bibcode") or "").strip()
    if bibcode:
        return f"bibcode:{bibcode}"

    return f"title:{_normalize_title(str(paper.get('title') or ''))}"


def _paper_year_sort_value(paper: Dict[str, Any]) -> int:
    """Extract year from published field to sort newest first."""
    published = str(paper.get("published") or "")
    match = re.search(r"(19|20)\d{2}", published)
    if not match:
        return 0
    try:
        return int(match.group(0))
    except ValueError:
        return 0


def _strip_xml_html_tags(text: str) -> str:
    """Remove simple XML/HTML tags from API-provided abstract strings."""
    raw = str(text or "").strip()
    if not raw:
        return ""
    clean = re.sub(r"<[^>]+>", " ", raw)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _xml_local_name(tag: str) -> str:
    return str(tag or "").split("}")[-1]


def _xml_text_values(node: ET.Element, local_name: str, max_items: int = 50) -> List[str]:
    out: List[str] = []
    expected = str(local_name or "").strip().lower()
    if not expected:
        return out
    for el in node.iter():
        if _xml_local_name(el.tag).lower() != expected:
            continue
        value = re.sub(r"\s+", " ", str(el.text or "").strip())
        if not value:
            continue
        out.append(value)
        if len(out) >= max_items:
            break
    return out


def _first_nonempty(values: List[str], default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def _extract_crossref_published(item: Dict[str, Any]) -> str:
    """Extract publication date from common Crossref date containers."""
    for key in ("published-print", "published-online", "issued", "created"):
        date_obj = item.get(key) or {}
        if not isinstance(date_obj, dict):
            continue
        parts = date_obj.get("date-parts") or []
        if not parts or not isinstance(parts, list):
            continue
        first = parts[0] if parts else []
        if not isinstance(first, list) or not first:
            continue
        try:
            year = int(first[0])
        except (TypeError, ValueError):
            continue
        month = int(first[1]) if len(first) > 1 and str(first[1]).isdigit() else 1
        day = int(first[2]) if len(first) > 2 and str(first[2]).isdigit() else 1
        return f"{year:04d}-{month:02d}-{day:02d}"
    return ""


def _extract_pubmed_doi(articleids: Any) -> str:
    """Extract DOI from PubMed `articleids` list."""
    if not isinstance(articleids, list):
        return ""
    for ref in articleids:
        if not isinstance(ref, dict):
            continue
        if str(ref.get("idtype") or "").lower() == "doi":
            return str(ref.get("value") or "").strip()
    return ""


def _get_unpaywall_email() -> Optional[str]:
    """Return contact email for Unpaywall requests."""
    mailto = (os.getenv("UNPAYWALL_MAILTO") or os.getenv("CROSSREF_MAILTO") or "").strip()
    if mailto:
        return mailto
    env_path = Path(__file__).resolve().parents[1] / '.env'
    vals = dotenv_values(env_path)
    mailto = (vals.get("UNPAYWALL_MAILTO") or vals.get("CROSSREF_MAILTO") or "").strip()
    if mailto:
        os.environ.setdefault("UNPAYWALL_MAILTO", mailto)
    return mailto or None


def _within_text(haystack: str, needle: str) -> bool:
    """Case-insensitive substring check."""
    return needle.lower() in (haystack or "").lower()


def _has_pdf(paper: Dict[str, Any]) -> bool:
    """Quick PDF check used for filtering/sorting."""
    url = str(paper.get("url") or "").lower()
    pdf_url = str(paper.get("pdf_url") or "").lower()
    return url.endswith(".pdf") or pdf_url.endswith(".pdf") or bool(pdf_url)


def _is_pdf_url(url: str) -> bool:
    raw = str(url or "").strip().lower()
    if not raw:
        return False
    return raw.endswith(".pdf") or "/pdf" in raw or "downloadpdf" in raw


def _normalize_doi(doi: str) -> str:
    cleaned = str(doi or "").strip()
    if not cleaned:
        return ""
    cleaned = cleaned.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
    cleaned = re.sub(r"^doi:\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def _paper_full_text_url_from_fields(
    pdf_url: Optional[str],
    institutional_url: Optional[str],
    url: Optional[str],
) -> str:
    pdf_value = str(pdf_url or "").strip()
    institutional_value = str(institutional_url or "").strip()
    url_value = str(url or "").strip()
    if pdf_value:
        return pdf_value
    if institutional_value:
        return institutional_value
    if _is_pdf_url(url_value):
        return url_value
    return ""


def _annotate_access_metadata(paper: Dict[str, Any]) -> Dict[str, Any]:
    source = str(paper.get("source") or "").strip().lower()
    doi = _normalize_doi(str(paper.get("doi") or ""))
    url = str(paper.get("url") or "").strip()
    pdf_url = str(paper.get("pdf_url") or "").strip()
    institutional_url = str(paper.get("institutional_url") or "").strip()

    full_text_url = _paper_full_text_url_from_fields(pdf_url, institutional_url, url)
    full_text_available = bool(full_text_url)

    if institutional_url and full_text_url == institutional_url and not pdf_url:
        access_type = "institutional"
        access_label = "Institutional Full Text"
    elif full_text_available and (source in OPEN_ACCESS_SOURCES or bool(pdf_url)):
        access_type = "open_access"
        access_label = "Open Full Text"
    elif full_text_available:
        access_type = "full_text_link"
        access_label = "Full Text Link"
    elif doi:
        access_type = "doi_only"
        access_label = "DOI Available"
    else:
        access_type = "metadata_only"
        access_label = "Metadata Only"

    paper["doi"] = doi or paper.get("doi") or ""
    paper["full_text_available"] = full_text_available
    paper["access_type"] = access_type
    paper["access_label"] = access_label
    if full_text_url:
        paper["full_text_url"] = full_text_url
    elif "full_text_url" in paper:
        paper.pop("full_text_url", None)
    return paper


def _looks_like_doi(token: str) -> str:
    text = str(token or "").strip()
    if not text:
        return ""
    match = re.search(r"(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", text)
    if not match:
        return ""
    return _normalize_doi(match.group(1))


def _entry_title_from_url(url: str) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    candidate = value.rstrip("/").split("/")[-1].replace("-", " ").replace("_", " ").strip()
    if not candidate:
        return "Imported paper"
    return candidate[:220]


def _parse_institutional_raw_text(raw_text: str) -> List[InstitutionalPaperEntry]:
    entries: List[InstitutionalPaperEntry] = []
    for raw_line in (raw_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue

        parts = [segment.strip() for segment in re.split(r"\s*\|\s*|\t", line) if segment.strip()]
        if not parts:
            continue

        title = parts[0]
        url = ""
        doi = ""
        authors: List[str] = []
        pdf_url = ""

        for token in parts[1:]:
            token_val = token.strip()
            if not token_val:
                continue
            if token_val.lower().startswith("http"):
                if not url:
                    url = token_val
                if _is_pdf_url(token_val) and not pdf_url:
                    pdf_url = token_val
                continue
            possible_doi = _looks_like_doi(token_val)
            if possible_doi and not doi:
                doi = possible_doi
                continue
            authors.append(token_val)

        if title.lower().startswith("http"):
            if not url:
                url = title
            title = _entry_title_from_url(url)

        title = re.sub(r"^\d+[\).\-\s]+", "", title).strip()[:600]
        if not title:
            continue

        entries.append(
            InstitutionalPaperEntry(
                title=title,
                url=url or None,
                doi=doi or None,
                authors=authors[:12] if authors else [],
                abstract="",
                pdf_url=pdf_url or None,
                institutional_url=url or None,
            )
        )
    return entries


def _global_cache_key(query: str, max_results: int, offset: int, search_mode: str = "balanced") -> str:
    """Build a stable cache key for a global search request."""
    mode = _normalize_search_mode(search_mode)
    normalized_query = re.sub(r"\s+", " ", str(query or "").strip().lower())
    return f"{mode}:{normalized_query}:{max_results}:{offset}"


def _global_cache_get(cache_key: str) -> Optional[Dict[str, Any]]:
    """Read a non-expired cache entry."""
    entry = _GLOBAL_SEARCH_CACHE.get(cache_key)
    if not entry:
        return None
    if time.time() > float(entry.get("expires_at", 0)):
        _GLOBAL_SEARCH_CACHE.pop(cache_key, None)
        return None
    payload = deepcopy(entry.get("payload") or {})
    payload["cache_hit"] = True
    return payload


def _global_cache_put(cache_key: str, payload: Dict[str, Any]) -> None:
    """Store a cache entry and evict oldest entries when capacity is exceeded."""
    _GLOBAL_SEARCH_CACHE[cache_key] = {
        "expires_at": time.time() + GLOBAL_SEARCH_CACHE_TTL_SECONDS,
        "stored_at": time.time(),
        "payload": deepcopy(payload),
    }
    if len(_GLOBAL_SEARCH_CACHE) <= GLOBAL_SEARCH_CACHE_MAX_ITEMS:
        return
    oldest_key = min(_GLOBAL_SEARCH_CACHE.items(), key=lambda kv: kv[1].get("stored_at", 0))[0]
    _GLOBAL_SEARCH_CACHE.pop(oldest_key, None)


def _log_search_event(event: str, **fields: Any) -> None:
    """Emit structured JSON logs for paper-search monitoring."""
    payload = {"event": event, **fields}
    try:
        logging.getLogger(__name__).info(json.dumps(payload, default=str))
    except Exception:
        logging.getLogger(__name__).info("search_event=%s fields=%s", event, str(fields))


def _normalize_search_mode(value: str) -> str:
    mode = str(value or "").strip().lower()
    if mode in GLOBAL_SEARCH_SOURCE_PRESETS:
        return mode
    return "balanced"


def _get_core_key() -> str:
    """Resolve CORE API key (optional, used for full-text/metadata)."""
    key = (os.getenv("CORE_API_KEY") or "").strip()
    if key:
        return key
    env_path = Path(__file__).resolve().parents[1] / '.env'
    vals = dotenv_values(env_path)
    key = (vals.get("CORE_API_KEY") or "").strip()
    if key:
        os.environ.setdefault("CORE_API_KEY", key)
    return key


async def _fetch_unpaywall_pdf(doi: str) -> Optional[str]:
    """Lookup an open-access PDF via Unpaywall; returns PDF URL or None."""
    doi_clean = (doi or "").strip()
    if not doi_clean:
        return None
    mailto = _get_unpaywall_email()
    params = {"email": mailto} if mailto else {}
    url = f"{UNPAYWALL_API}{doi_clean}"
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            resp = await client.get(url, params=params, headers={"User-Agent": "ResearchHub-AI/1.0"})
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError:
        return None

    best = data.get("best_oa_location") or {}
    pdf_url = best.get("url_for_pdf") or best.get("url")
    if not pdf_url:
        # fall back to any oa_location with pdf
        for loc in data.get("oa_locations") or []:
            pdf_url = loc.get("url_for_pdf") or loc.get("url")
            if pdf_url:
                break
    return pdf_url


# ---------------------------------------------------------------------------
# ArXiv helpers
# ---------------------------------------------------------------------------

def parse_arxiv_feed(xml_text: str) -> Tuple[list, Optional[int]]:
    """Parse ArXiv Atom feed into papers and total matches."""
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
    }
    root = ET.fromstring(xml_text)
    papers = []
    total_results: Optional[int] = None
    total_text = root.findtext("opensearch:totalResults", "", ns)
    if total_text:
        try:
            total_results = int(total_text)
        except ValueError:
            total_results = None
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
    return papers, total_results


# ---------------------------------------------------------------------------
# ArXiv search
# ---------------------------------------------------------------------------

@router.get("/search")
async def search_papers(
    query: str,
    max_results: int = 30,
    offset: int = 0,
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

    page_size = max(1, min(max_results, 100))
    start_offset = max(0, offset)

    params = {
        "search_query": search_query,
        "start": start_offset,
        "max_results": page_size,
        "sortBy": sort,
        "sortOrder": "descending",
    }

    # Retry with bounded timeouts to keep search responsive.
    last_error = None
    for timeout_secs in (10, 14):
        try:
            async with httpx.AsyncClient(timeout=timeout_secs) as client:
                response = await client.get(ARXIV_API, params=params)
                response.raise_for_status()
            papers, total = parse_arxiv_feed(response.text)
            returned = len(papers)
            next_offset = start_offset + returned
            has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
            return {
                "papers": papers,
                "total": total,
                "returned": returned,
                "offset": start_offset,
                "next_offset": next_offset,
                "has_more": has_more,
                "source": "arxiv",
            }
        except httpx.TimeoutException as e:
            last_error = f"ArXiv timed out ({timeout_secs}s). Try again or switch to Semantic Scholar."
            continue
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"ArXiv API error: {str(e)}")
        except ET.ParseError as e:
            raise HTTPException(status_code=502, detail=f"Failed to parse ArXiv response: {str(e)}")

    # Keep search usable even if ArXiv is temporarily slow/unreachable.
    # This prevents hard failures in local/dev and provides users with an
    # actionable response while upstream recovers.
    fallback_paper = {
        "title": f"ArXiv temporarily unavailable for: {query}",
        "authors": ["ResearchHub AI"],
        "abstract": (
            "ArXiv did not respond in time. Retry in a moment, or use the global "
            "search endpoint for merged results across other sources."
        ),
        "url": "",
        "published": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "categories": ["availability", "fallback"],
        "source": "arxiv",
    }
    return {
        "papers": [fallback_paper],
        "total": 1,
        "returned": 1,
        "offset": start_offset,
        "next_offset": start_offset + 1,
        "has_more": False,
        "source": "arxiv",
        "notice": last_error or "ArXiv timed out. Showing fallback result.",
    }


# ---------------------------------------------------------------------------
# Semantic Scholar search  (200M+ papers, all disciplines, free — no key)
# ---------------------------------------------------------------------------

@router.get("/search-semantic")
async def search_semantic(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    allow_fallback_arxiv: bool = True,
    current_user: User = Depends(get_current_user),
):
    """Search Semantic Scholar — 200M+ papers across all disciplines. No API key needed."""
    page_size = max(1, min(max_results, 100))
    start_offset = max(0, offset)
    semantic_key = _get_semantic_key()
    params = {
        "query": query,
        "limit": page_size,
        "offset": start_offset,
        "fields": "title,authors,abstract,year,externalIds,publicationTypes,openAccessPdf,url",
    }
    headers = {"User-Agent": "ResearchHub-AI/1.0"}
    if semantic_key:
        headers["x-api-key"] = semantic_key
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                SEMANTIC_SCHOLAR_API,
                params=params,
                headers=headers,
            )
            response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Semantic Scholar timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            if allow_fallback_arxiv:
                # Graceful fallback: when Semantic Scholar throttles, return ArXiv results
                # instead of hard-failing the search flow.
                fallback_params = {
                    "search_query": f"all:{query}",
                    "start": start_offset,
                    "max_results": page_size,
                    "sortBy": "relevance",
                    "sortOrder": "descending",
                }
                try:
                    async with httpx.AsyncClient(timeout=20) as client:
                        fallback_response = await client.get(ARXIV_API, params=fallback_params)
                        fallback_response.raise_for_status()
                    papers, total = parse_arxiv_feed(fallback_response.text)
                    returned = len(papers)
                    next_offset = start_offset + returned
                    has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
                    return {
                        "papers": papers,
                        "total": total,
                        "returned": returned,
                        "offset": start_offset,
                        "next_offset": next_offset,
                        "has_more": has_more,
                        "source": "semantic_scholar_fallback_arxiv",
                        "notice": "Semantic Scholar is rate-limited right now. Showing ArXiv results temporarily.",
                    }
                except (httpx.HTTPError, ET.ParseError):
                    raise HTTPException(
                        status_code=429,
                        detail="Semantic Scholar rate limit reached. Please retry shortly or switch source.",
                    )
            raise HTTPException(
                status_code=429,
                detail="Semantic Scholar rate limit reached. Please retry shortly.",
            )
        if e.response.status_code in (401, 403):
            raise HTTPException(
                status_code=401,
                detail="Semantic Scholar API key rejected. Check SEMANTIC_SCHOLAR_API_KEY.",
            )
        raise HTTPException(status_code=502, detail="Semantic Scholar API upstream error.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Semantic Scholar API error.")

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

    total = data.get("total")
    returned = len(papers)
    next_offset = start_offset + returned
    has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
    return {
        "papers": papers,
        "total": total,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "semantic_scholar",
    }


# ---------------------------------------------------------------------------
# OpenAlex search (250M+ works, broad multi-discipline index)
# ---------------------------------------------------------------------------

@router.get("/search-openalex")
async def search_openalex(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search OpenAlex for research works across broad disciplines."""
    page_size = max(1, min(max_results, 100))
    start_offset = max(0, offset)
    page = (start_offset // page_size) + 1
    mailto = (os.getenv("OPENALEX_MAILTO") or "").strip()

    params = {
        "search": query,
        "per-page": page_size,
        "page": page,
        "select": "id,display_name,authorships,abstract_inverted_index,publication_year,doi,primary_location,concepts,type",
    }
    if mailto:
        params["mailto"] = mailto

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                OPENALEX_API,
                params=params,
                headers={"User-Agent": "ResearchHub-AI/1.0"},
            )
            response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="OpenAlex timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="OpenAlex rate limit reached. Please retry shortly or reduce results per page.",
            )
        raise HTTPException(status_code=502, detail="OpenAlex API upstream error.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="OpenAlex API error.")

    papers = []
    for item in data.get("results", []):
        authors = []
        for authorship in item.get("authorships") or []:
            author = (authorship or {}).get("author") or {}
            name = author.get("display_name") or ""
            if name:
                authors.append(name)

        abstract = _decode_openalex_abstract(item.get("abstract_inverted_index"))
        published_year = item.get("publication_year")
        published = str(published_year) if published_year else ""

        doi_raw = item.get("doi") or ""
        doi = (
            str(doi_raw)
            .replace("https://doi.org/", "")
            .replace("http://doi.org/", "")
            .strip()
        )

        url = ""
        primary_location = item.get("primary_location") or {}
        if isinstance(primary_location, dict):
            url = primary_location.get("landing_page_url") or primary_location.get("pdf_url") or ""
        if not url and doi:
            url = f"https://doi.org/{doi}"

        concepts = item.get("concepts") or []
        categories = []
        work_type = item.get("type") or ""
        if work_type:
            categories.append(work_type)
        for concept in concepts:
            label = (concept or {}).get("display_name", "")
            if label:
                categories.append(label)
            if len(categories) >= 3:
                break

        papers.append({
            "title": item.get("display_name") or "",
            "authors": authors,
            "abstract": abstract,
            "url": url,
            "published": published,
            "categories": categories,
            "doi": doi,
            "source": "openalex",
        })

    meta = data.get("meta") or {}
    total = meta.get("count")
    returned = len(papers)
    next_offset = start_offset + returned
    has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
    return {
        "papers": papers,
        "total": total,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "openalex",
    }


# ---------------------------------------------------------------------------
# Europe PMC search (open access biomedical literature)
# ---------------------------------------------------------------------------

@router.get("/search-europepmc")
async def search_europepmc(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search Europe PMC public API (open access biomedical literature)."""
    page_size = max(1, min(max_results, 100))
    start_offset = max(0, offset)
    page = (start_offset // page_size) + 1

    params = {
        "query": query,
        "format": "json",
        "pageSize": page_size,
        "page": page,
        "resultType": "core",
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                EUROPE_PMC_API,
                params=params,
                headers={"User-Agent": "ResearchHub-AI/1.0"},
            )
            response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Europe PMC timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="Europe PMC rate limit reached. Please retry shortly.",
            )
        raise HTTPException(status_code=502, detail="Europe PMC API upstream error.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Europe PMC API error.")

    result_list = (data.get("resultList") or {}).get("result") or []
    papers = []
    for item in result_list:
        authors = []
        author_list = item.get("authorList") or {}
        if isinstance(author_list, dict):
            for author in author_list.get("author") or []:
                name = (author or {}).get("fullName") or (author or {}).get("collectiveName") or ""
                if name:
                    authors.append(name)

        if not authors:
            raw_author = (item.get("authorString") or "").strip()
            if raw_author:
                authors = [a.strip() for a in raw_author.replace(";", ",").split(",") if a.strip()][:10]

        abstract = item.get("abstractText") or "No abstract available."
        published = (
            item.get("firstPublicationDate")
            or item.get("firstIndexDate")
            or item.get("pubYear")
            or ""
        )
        if isinstance(published, str):
            published = published[:10]
        else:
            published = str(published)

        doi = (item.get("doi") or "").strip()
        pmcid = (item.get("pmcid") or "").strip()
        source = (item.get("source") or "").strip().lower()
        source_id = (item.get("id") or "").strip()

        if doi:
            url = f"https://doi.org/{doi}"
        elif pmcid:
            url = f"https://europepmc.org/articles/{pmcid}"
        elif source and source_id:
            url = f"https://europepmc.org/article/{source}/{source_id}"
        else:
            url = ""

        categories = []
        pub_type = (item.get("pubType") or "").strip()
        journal_title = (item.get("journalTitle") or "").strip()
        if pub_type:
            categories.append(pub_type)
        if journal_title:
            categories.append(journal_title)

        papers.append({
            "title": (item.get("title") or "").strip(),
            "authors": authors,
            "abstract": abstract,
            "url": url,
            "published": published,
            "categories": categories[:3],
            "doi": doi,
            "source": "europe_pmc",
        })

    total = data.get("hitCount")
    try:
        total = int(total) if total is not None else None
    except (TypeError, ValueError):
        total = None

    returned = len(papers)
    next_offset = start_offset + returned
    has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
    return {
        "papers": papers,
        "total": total,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "europe_pmc",
    }


# ---------------------------------------------------------------------------
# Crossref search (large DOI registry metadata index)
# ---------------------------------------------------------------------------

@router.get("/search-crossref")
async def search_crossref(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search Crossref works API for broad scholarly metadata."""
    page_size = max(1, min(max_results, 100))
    start_offset = max(0, offset)
    mailto = (os.getenv("CROSSREF_MAILTO") or "").strip()

    params: Dict[str, Any] = {
        "query": query,
        "rows": page_size,
        "offset": start_offset,
        "select": "title,author,abstract,DOI,URL,published-print,published-online,issued,created,container-title,type",
    }
    if mailto:
        params["mailto"] = mailto

    user_agent = "ResearchHub-AI/1.0"
    if mailto:
        user_agent = f"ResearchHub-AI/1.0 (mailto:{mailto})"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                CROSSREF_API,
                params=params,
                headers={"User-Agent": user_agent},
            )
            response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Crossref timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="Crossref rate limit reached. Please retry shortly.")
        raise HTTPException(status_code=502, detail="Crossref API upstream error.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Crossref API error.")

    message = data.get("message") or {}
    items = message.get("items") or []
    papers = []

    for item in items:
        title_raw = item.get("title") or []
        title = title_raw[0] if isinstance(title_raw, list) and title_raw else str(title_raw or "")

        authors = []
        for author in item.get("author") or []:
            if not isinstance(author, dict):
                continue
            given = str(author.get("given") or "").strip()
            family = str(author.get("family") or "").strip()
            full_name = f"{given} {family}".strip()
            if not full_name:
                full_name = str(author.get("name") or "").strip()
            if full_name:
                authors.append(full_name)

        abstract = _strip_xml_html_tags(item.get("abstract") or "")
        if not abstract:
            abstract = "No abstract available."

        doi = str(item.get("DOI") or "").strip()
        url = str(item.get("URL") or "").strip()
        if not url and doi:
            url = f"https://doi.org/{doi}"

        container = item.get("container-title") or []
        journal_title = container[0] if isinstance(container, list) and container else ""
        work_type = str(item.get("type") or "").strip()
        categories = [x for x in [work_type, journal_title] if x][:3]

        papers.append({
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "url": url,
            "published": _extract_crossref_published(item),
            "categories": categories,
            "doi": doi,
            "publication_name": journal_title,
            "source": "crossref",
        })

    total = message.get("total-results")
    try:
        total = int(total) if total is not None else None
    except (TypeError, ValueError):
        total = None

    returned = len(papers)
    next_offset = start_offset + returned
    has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
    return {
        "papers": papers,
        "total": total,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "crossref",
    }


# ---------------------------------------------------------------------------
# PubMed search (NCBI E-utilities)
# ---------------------------------------------------------------------------

@router.get("/search-pubmed")
async def search_pubmed(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search PubMed using ESearch + ESummary for broad biomedical coverage."""
    page_size = max(1, min(max_results, 100))
    start_offset = max(0, offset)
    ncbi_key = (os.getenv("NCBI_API_KEY") or "").strip()

    search_params: Dict[str, Any] = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retstart": start_offset,
        "retmax": page_size,
        "sort": "relevance",
    }
    if ncbi_key:
        search_params["api_key"] = ncbi_key

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            search_response = await client.get(PUBMED_ESEARCH_API, params=search_params)
            search_response.raise_for_status()
        search_data = search_response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="PubMed timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="PubMed rate limit reached. Please retry shortly.")
        raise HTTPException(status_code=502, detail="PubMed API upstream error.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="PubMed API error.")

    esearch = search_data.get("esearchresult") or {}
    id_list = esearch.get("idlist") or []
    total = esearch.get("count")
    try:
        total = int(total) if total is not None else None
    except (TypeError, ValueError):
        total = None

    if not id_list:
        return {
            "papers": [],
            "total": total,
            "returned": 0,
            "offset": start_offset,
            "next_offset": start_offset,
            "has_more": False,
            "source": "pubmed",
        }

    summary_params: Dict[str, Any] = {
        "db": "pubmed",
        "retmode": "json",
        "id": ",".join(str(x) for x in id_list),
    }
    if ncbi_key:
        summary_params["api_key"] = ncbi_key

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            summary_response = await client.get(PUBMED_ESUMMARY_API, params=summary_params)
            summary_response.raise_for_status()
        summary_data = summary_response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="PubMed summary timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="PubMed rate limit reached. Please retry shortly.")
        raise HTTPException(status_code=502, detail="PubMed summary API upstream error.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="PubMed summary API error.")

    summary_result = summary_data.get("result") or {}
    uids = summary_result.get("uids") or id_list
    papers = []

    for uid in uids:
        key = str(uid)
        item = summary_result.get(key) or {}
        title = str(item.get("title") or "").strip()
        if not title:
            continue

        authors = []
        for author in item.get("authors") or []:
            if not isinstance(author, dict):
                continue
            name = str(author.get("name") or "").strip()
            if name:
                authors.append(name)

        doi = _extract_pubmed_doi(item.get("articleids"))
        url = f"https://pubmed.ncbi.nlm.nih.gov/{key}/"
        journal = str(item.get("fulljournalname") or item.get("source") or "").strip()
        pubdate = str(item.get("pubdate") or item.get("sortpubdate") or "").strip()
        if len(pubdate) > 10 and re.match(r"^\d{4}-\d{2}-\d{2}", pubdate):
            pubdate = pubdate[:10]

        categories = []
        doc_type = item.get("doctype")
        if isinstance(doc_type, str) and doc_type.strip():
            categories.append(doc_type.strip())
        pub_type = item.get("pubtype") or []
        if isinstance(pub_type, list):
            for entry in pub_type:
                label = str(entry or "").strip()
                if label:
                    categories.append(label)
                if len(categories) >= 2:
                    break
        if journal:
            categories.append(journal)

        papers.append({
            "title": title,
            "authors": authors,
            "abstract": "No abstract available.",
            "url": url,
            "published": pubdate,
            "categories": categories[:3],
            "doi": doi,
            "publication_name": journal,
            "source": "pubmed",
        })

    returned = len(papers)
    next_offset = start_offset + returned
    has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
    return {
        "papers": papers,
        "total": total,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "pubmed",
    }


# ---------------------------------------------------------------------------
# DOAJ search (Directory of Open Access Journals)
# ---------------------------------------------------------------------------

@router.get("/search-doaj")
async def search_doaj(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search DOAJ open-access article index."""
    page_size = max(1, min(max_results, 100))
    start_offset = max(0, offset)
    page = (start_offset // page_size) + 1
    encoded_query = quote(query.strip(), safe="")
    url = f"{DOAJ_API_BASE}/{encoded_query}"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                url,
                params={"page": page, "pageSize": page_size},
                headers={"User-Agent": "ResearchHub-AI/1.0"},
            )
            response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="DOAJ timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="DOAJ rate limit reached. Please retry shortly.")
        raise HTTPException(status_code=502, detail="DOAJ API upstream error.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="DOAJ API error.")

    results = data.get("results") or []
    papers = []

    for item in results:
        bib = item.get("bibjson") or {}
        title = str(bib.get("title") or "").strip()
        if not title:
            continue

        authors = []
        for author in bib.get("author") or []:
            if not isinstance(author, dict):
                continue
            name = str(author.get("name") or "").strip()
            if name:
                authors.append(name)

        abstract = str(bib.get("abstract") or "").strip() or "No abstract available."
        year = str(bib.get("year") or "").strip()
        month = str(bib.get("month") or "").strip()
        published = year
        if year and month and month.isdigit():
            published = f"{year}-{int(month):02d}"

        doi = ""
        for identifier in bib.get("identifier") or []:
            if not isinstance(identifier, dict):
                continue
            if str(identifier.get("type") or "").lower() == "doi":
                doi = str(identifier.get("id") or "").strip()
                break

        url = ""
        for link in bib.get("link") or []:
            if not isinstance(link, dict):
                continue
            candidate = str(link.get("url") or "").strip()
            if candidate:
                url = candidate
                break
        if not url and doi:
            url = f"https://doi.org/{doi}"

        journal = str((bib.get("journal") or {}).get("title") or "").strip()
        keywords = [str(k).strip() for k in (bib.get("keywords") or []) if str(k).strip()]
        categories = [x for x in [journal, *keywords[:2]] if x][:3]

        papers.append({
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "url": url,
            "published": published,
            "categories": categories,
            "doi": doi,
            "publication_name": journal,
            "source": "doaj",
        })

    total = data.get("total")
    try:
        total = int(total) if total is not None else None
    except (TypeError, ValueError):
        total = None

    returned = len(papers)
    next_offset = start_offset + returned
    has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
    return {
        "papers": papers,
        "total": total,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "doaj",
    }


# ---------------------------------------------------------------------------
# HAL (French open archive) search
# ---------------------------------------------------------------------------

@router.get("/search-hal")
async def search_hal(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search HAL open archive (broad science/engineering, OA)."""
    page_size = max(1, min(max_results, 100))
    start_offset = max(0, offset)

    params = {
        "q": query,
        "wt": "json",
        "fl": "title_s,abstract_s,authFullName_s,doiId_s,linkExtUrl_s,publicationDateY_i",
        "rows": page_size,
        "start": start_offset,
        "sort": "score desc",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(HAL_API_SEARCH, params=params, headers={"User-Agent": "ResearchHub-AI/1.0"})
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="HAL timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="HAL rate limit reached. Please retry shortly.")
        raise HTTPException(status_code=502, detail="HAL API upstream error.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="HAL API error.")

    docs = ((data.get("response") or {}).get("docs")) or []
    total = (data.get("response") or {}).get("numFound")
    try:
        total = int(total) if total is not None else None
    except (TypeError, ValueError):
        total = None

    papers = []
    for doc in docs:
        title = ""
        if isinstance(doc.get("title_s"), list):
            title = doc.get("title_s")[0] or ""
        elif isinstance(doc.get("title_s"), str):
            title = doc.get("title_s")
        title = title.strip()
        if not title:
            continue

        authors = []
        raw_auth = doc.get("authFullName_s") or []
        if isinstance(raw_auth, list):
            authors = [str(a).strip() for a in raw_auth if str(a).strip()]

        abstract = ""
        raw_abs = doc.get("abstract_s")
        if isinstance(raw_abs, list) and raw_abs:
            abstract = raw_abs[0]
        elif isinstance(raw_abs, str):
            abstract = raw_abs
        abstract = abstract.strip() or "No abstract available."

        doi = ""
        raw_doi = doc.get("doiId_s")
        if isinstance(raw_doi, list) and raw_doi:
            doi = str(raw_doi[0]).strip()
        elif isinstance(raw_doi, str):
            doi = raw_doi.strip()

        url = ""
        raw_url = doc.get("linkExtUrl_s")
        if isinstance(raw_url, list) and raw_url:
            url = str(raw_url[0]).strip()
        elif isinstance(raw_url, str):
            url = raw_url.strip()
        if not url and doi:
            url = f"https://doi.org/{doi}"

        year = doc.get("publicationDateY_i") or ""
        published = str(year) if year else ""

        papers.append({
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "url": url,
            "published": published,
            "categories": [],
            "doi": doi,
            "source": "hal",
        })

    returned = len(papers)
    next_offset = start_offset + returned
    has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
    return {
        "papers": papers,
        "total": total,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "hal",
    }


# ---------------------------------------------------------------------------
# bioRxiv / medRxiv search (keyword filter over recent preprints)
# ---------------------------------------------------------------------------

async def _search_rxiv(server: str, query: str, max_results: int, lookback_days: int = 365):
    """Search bioRxiv or medRxiv by pulling recent preprints and keyword-filtering."""
    page_size = max(1, min(max_results, 60))
    start_date = (date.today() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    end_date = date.today().strftime("%Y-%m-%d")
    collected = []
    cursor = 0
    query_l = query.lower()

    while len(collected) < max_results and cursor < 180:  # max ~3 pages of 60
        url = f"{BIORXIV_API_BASE}/{server}/{start_date}/{end_date}/{cursor}"
        try:
            async with httpx.AsyncClient(timeout=6) as client:
                resp = await client.get(url, headers={"User-Agent": "ResearchHub-AI/1.0"})
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError:
            break

        records = data.get("collection") or []
        if not records:
            break

        for rec in records:
            title = (rec.get("title") or "").strip()
            abstract = (rec.get("abstract") or "").strip()
            if not title:
                continue
            if query_l not in title.lower() and query_l not in abstract.lower():
                continue
            authors = [a.strip() for a in (rec.get("authors") or "").split(";") if a.strip()]
            doi = (rec.get("doi") or "").replace("http://dx.doi.org/", "").replace("https://doi.org/", "").strip()
            url_full = f"https://doi.org/{doi}" if doi else (rec.get("link") or "").strip()
            published = (rec.get("date") or "")[:10]
            source_label = "biorxiv" if server == "biorxiv" else "medrxiv"
            collected.append({
                "title": title,
                "authors": authors,
                "abstract": abstract or "No abstract available.",
                "url": url_full,
                "pdf_url": rec.get("link"),
                "published": published,
                "categories": [rec.get("category") or ""],
                "doi": doi,
                "source": source_label,
            })
            if len(collected) >= max_results:
                break

        cursor += page_size

    return collected[:max_results]


@router.get("/search-biorxiv")
async def search_biorxiv(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search bioRxiv preprints (keyword filtered over recent year)."""
    results = await _search_rxiv("biorxiv", query, max_results)
    returned = len(results)
    return {
        "papers": results,
        "total": None,
        "returned": returned,
        "offset": offset,
        "next_offset": offset + returned,
        "has_more": returned >= max_results,
        "source": "biorxiv",
    }


@router.get("/search-medrxiv")
async def search_medrxiv(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search medRxiv preprints (keyword filtered over recent year)."""
    results = await _search_rxiv("medrxiv", query, max_results)
    returned = len(results)
    return {
        "papers": results,
        "total": None,
        "returned": returned,
        "offset": offset,
        "next_offset": offset + returned,
        "has_more": returned >= max_results,
        "source": "medrxiv",
    }


# ---------------------------------------------------------------------------
# PLOS search (open access journals)
# ---------------------------------------------------------------------------

@router.get("/search-plos")
async def search_plos(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search PLOS (Public Library of Science) OA journals."""
    page_size = max(1, min(max_results, 50))
    start_offset = max(0, offset)
    params = {
        "q": f"title:{query} OR abstract:{query}",
        "rows": page_size,
        "start": start_offset,
        "fl": "id,title,author,abstract,publication_date,journal,doi",
    }
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(PLOS_API, params=params, headers={"User-Agent": "ResearchHub-AI/1.0"})
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="PLOS timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="PLOS rate limit reached. Please retry shortly.")
        raise HTTPException(status_code=502, detail="PLOS API upstream error.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="PLOS API error.")

    docs = (data.get("response") or {}).get("docs") or []
    total = (data.get("response") or {}).get("numFound")
    try:
        total = int(total) if total is not None else None
    except (TypeError, ValueError):
        total = None

    papers = []
    def _first_text(value: Any) -> str:
        if isinstance(value, list):
            value = value[0] if value else ""
        elif isinstance(value, dict):
            value = value.get("value") or value.get("name") or value.get("display_name") or ""
        return str(value or "").strip()

    for doc in docs:
        title = _first_text(doc.get("title"))
        if not title:
            continue
        authors = [a for a in doc.get("author") or []]
        abstract = (doc.get("abstract") or "")
        if isinstance(abstract, list):
            abstract = abstract[0] if abstract else ""
        abstract = (abstract or "No abstract available.").strip()
        pub_date = (doc.get("publication_date") or "")[:10]
        doi = _first_text(doc.get("doi"))
        url = f"https://doi.org/{doi}" if doi else ""
        journal = _first_text(doc.get("journal"))
        papers.append({
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "url": url,
            "published": pub_date,
            "categories": [journal] if journal else [],
            "doi": doi,
            "publication_name": journal,
            "source": "plos",
        })

    returned = len(papers)
    next_offset = start_offset + returned
    has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
    return {
        "papers": papers,
        "total": total,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "plos",
    }


# ---------------------------------------------------------------------------
# eLife search (via Europe PMC journal filter)
# ---------------------------------------------------------------------------

@router.get("/search-elife")
async def search_elife(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search eLife articles via Europe PMC."""
    page_size = max(1, min(max_results, 50))
    start_offset = max(0, offset)
    page = (start_offset // page_size) + 1
    params = {
        "query": f"{query} JOURNAL:\"eLife\"",
        "format": "json",
        "pageSize": page_size,
        "page": page,
        "resultType": "core",
    }
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(EUROPE_PMC_API, params=params, headers={"User-Agent": "ResearchHub-AI/1.0"})
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="eLife (via Europe PMC) timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="Europe PMC rate limit reached. Please retry shortly.")
        raise HTTPException(status_code=502, detail="eLife upstream error.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="eLife API error.")

    result_list = (data.get("resultList") or {}).get("result") or []
    papers = []
    for item in result_list:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        authors = []
        author_list = item.get("authorList") or {}
        if isinstance(author_list, dict):
            for author in author_list.get("author") or []:
                nm = (author or {}).get("fullName") or (author or {}).get("collectiveName") or ""
                if nm:
                    authors.append(nm)
        abstract = item.get("abstractText") or "No abstract available."
        published = (
            item.get("firstPublicationDate")
            or item.get("firstIndexDate")
            or item.get("pubYear")
            or ""
        )
        if isinstance(published, str):
            published = published[:10]
        else:
            published = str(published)
        doi = (item.get("doi") or "").strip()
        url = f"https://doi.org/{doi}" if doi else (item.get("fullTextUrlList") or {}).get("fullTextUrl", [{}])[0].get("url", "")

        papers.append({
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "url": url,
            "published": published,
            "categories": ["eLife"],
            "doi": doi,
            "publication_name": "eLife",
            "source": "elife",
        })

    total = data.get("hitCount")
    try:
        total = int(total) if total is not None else None
    except (TypeError, ValueError):
        total = None

    returned = len(papers)
    next_offset = start_offset + returned
    has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
    return {
        "papers": papers,
        "total": total,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "elife",
    }


# ---------------------------------------------------------------------------
# DataCite search (open metadata for DOI-registered research outputs)
# ---------------------------------------------------------------------------

@router.get("/search-datacite")
async def search_datacite(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search DataCite works index."""
    page_size = max(1, min(max_results, 100))
    start_offset = max(0, offset)
    page = (start_offset // page_size) + 1

    params = {
        "query": query,
        "page[size]": page_size,
        "page[number]": page,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                DATACITE_WORKS_API,
                params=params,
                headers={"User-Agent": "ResearchHub-AI/1.0"},
            )
            response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="DataCite timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="DataCite rate limit reached. Please retry shortly.")
        raise HTTPException(status_code=502, detail="DataCite API upstream error.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="DataCite API error.")

    records = data.get("data") or []
    papers = []

    for record in records:
        attrs = record.get("attributes") or {}
        title = str(attrs.get("title") or "").strip()
        if not title:
            continue

        authors = []
        for author in attrs.get("author") or []:
            if not isinstance(author, dict):
                continue
            given = str(author.get("given") or "").strip()
            family = str(author.get("family") or "").strip()
            full_name = f"{given} {family}".strip()
            if not full_name:
                full_name = str(author.get("name") or "").strip()
            if full_name:
                authors.append(full_name)

        description = _strip_xml_html_tags(attrs.get("description") or "")
        if not description:
            description = "No abstract available."

        doi = str(attrs.get("doi") or "").strip()
        url = str(attrs.get("url") or "").strip()
        if not url and doi:
            url = f"https://doi.org/{doi}"

        published_raw = str(attrs.get("published") or attrs.get("registered") or "").strip()
        published = published_raw[:10] if len(published_raw) >= 10 else published_raw

        container = str(attrs.get("container-title") or "").strip()
        resource_type = str(attrs.get("resource-type-subtype") or attrs.get("resource-type-id") or "").strip()
        categories = [x for x in [resource_type, container] if x][:3]

        papers.append({
            "title": title,
            "authors": authors,
            "abstract": description,
            "url": url,
            "published": published,
            "categories": categories,
            "doi": doi,
            "publication_name": container,
            "source": "datacite",
        })

    meta = data.get("meta") or {}
    total = meta.get("total")
    try:
        total = int(total) if total is not None else None
    except (TypeError, ValueError):
        total = None

    returned = len(papers)
    next_offset = start_offset + returned
    has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
    return {
        "papers": papers,
        "total": total,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "datacite",
    }


def _extract_dblp_author_names(raw_authors: Any) -> List[str]:
    if isinstance(raw_authors, dict):
        raw_authors = raw_authors.get("author")
    if isinstance(raw_authors, str):
        raw_authors = [raw_authors]
    elif isinstance(raw_authors, dict):
        raw_authors = [raw_authors]
    if not isinstance(raw_authors, list):
        return []

    authors: List[str] = []
    for item in raw_authors:
        if isinstance(item, dict):
            name = str(item.get("text") or item.get("@text") or item.get("name") or "").strip()
        else:
            name = str(item or "").strip()
        if not name or name in authors:
            continue
        authors.append(name)
        if len(authors) >= 12:
            break
    return authors


# ---------------------------------------------------------------------------
# DBLP search (computer science bibliography)
# ---------------------------------------------------------------------------

@router.get("/search-dblp")
async def search_dblp(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search DBLP publication index."""
    page_size = max(1, min(max_results, 100))
    start_offset = max(0, offset)
    params = {
        "q": query,
        "h": page_size,
        "f": start_offset,
        "format": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                DBLP_API,
                params=params,
                headers={"User-Agent": "ResearchHub-AI/1.0"},
            )
            response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="DBLP timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="DBLP rate limit reached. Please retry shortly.")
        raise HTTPException(status_code=502, detail="DBLP API upstream error.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="DBLP API error.")

    result = data.get("result") or {}
    hits = result.get("hits") or {}
    raw_items = hits.get("hit") or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]

    papers = []
    for row in raw_items:
        info = row.get("info") if isinstance(row, dict) else {}
        if not isinstance(info, dict):
            continue

        title = str(info.get("title") or "").strip()
        if not title:
            continue

        doi = _normalize_doi(str(info.get("doi") or ""))
        ee_field = info.get("ee")
        ee_url = ""
        if isinstance(ee_field, list):
            ee_url = str(ee_field[0] or "").strip() if ee_field else ""
        elif isinstance(ee_field, str):
            ee_url = ee_field.strip()
        url = ee_url or str(info.get("url") or "").strip()
        if not url and doi:
            url = f"https://doi.org/{doi}"

        year = str(info.get("year") or "").strip()
        published = f"{year}-01-01" if re.fullmatch(r"\d{4}", year) else year
        venue = str(info.get("venue") or "").strip()
        publication_type = str(info.get("type") or "").strip()
        categories = [item for item in [venue, publication_type] if item][:3]

        papers.append(
            {
                "title": title,
                "authors": _extract_dblp_author_names(info.get("authors")),
                "abstract": "No abstract available.",
                "url": url,
                "published": published,
                "categories": categories,
                "doi": doi,
                "publication_name": venue,
                "source": "dblp",
            }
        )

    total = hits.get("@total") if isinstance(hits, dict) else None
    try:
        total = int(total) if total is not None else None
    except (TypeError, ValueError):
        total = None

    returned = len(papers)
    next_offset = start_offset + returned
    has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
    return {
        "papers": papers,
        "total": total,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "dblp",
    }


# ---------------------------------------------------------------------------
# Zenodo search (open repository records)
# ---------------------------------------------------------------------------

@router.get("/search-zenodo")
async def search_zenodo(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search Zenodo records and return publication-like entries."""
    page_size = max(1, min(max_results, 100))
    start_offset = max(0, offset)
    page = (start_offset // page_size) + 1
    params = {
        "q": query,
        "page": page,
        "size": page_size,
        "sort": "mostrecent",
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                ZENODO_API,
                params=params,
                headers={"User-Agent": "ResearchHub-AI/1.0"},
            )
            response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Zenodo timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="Zenodo rate limit reached. Please retry shortly.")
        raise HTTPException(status_code=502, detail="Zenodo API upstream error.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Zenodo API error.")

    hits = data.get("hits") or {}
    raw_items = hits.get("hits") or []
    papers = []

    for row in raw_items:
        metadata = row.get("metadata") if isinstance(row, dict) else {}
        if not isinstance(metadata, dict):
            continue
        title = str(metadata.get("title") or "").strip()
        if not title:
            continue

        creators = metadata.get("creators") or []
        authors = []
        if isinstance(creators, list):
            for creator in creators:
                if not isinstance(creator, dict):
                    continue
                name = str(creator.get("name") or "").strip()
                if not name:
                    continue
                authors.append(name)
                if len(authors) >= 12:
                    break

        description = _strip_xml_html_tags(metadata.get("description") or "")
        if not description:
            description = "No abstract available."

        doi = _normalize_doi(str(row.get("doi") or metadata.get("doi") or ""))
        links = row.get("links") if isinstance(row.get("links"), dict) else {}
        url = str(links.get("html") or links.get("self_html") or links.get("record_html") or "").strip()
        if not url:
            rec_id = row.get("id")
            if rec_id is not None:
                url = f"https://zenodo.org/records/{rec_id}"
        if not url and doi:
            url = f"https://doi.org/{doi}"

        pdf_url = ""
        for file_obj in row.get("files") or []:
            if not isinstance(file_obj, dict):
                continue
            file_links = file_obj.get("links") if isinstance(file_obj.get("links"), dict) else {}
            candidate = str(file_links.get("self") or file_links.get("download") or "").strip()
            key = str(file_obj.get("key") or "").strip()
            if not candidate and key.endswith(".pdf"):
                rec_id = row.get("id")
                if rec_id is not None:
                    candidate = f"https://zenodo.org/records/{rec_id}/files/{key}?download=1"
            if candidate and _is_pdf_url(candidate):
                pdf_url = candidate
                break

        resource_type_obj = metadata.get("resource_type") or {}
        resource_type = ""
        if isinstance(resource_type_obj, dict):
            resource_type = str(
                resource_type_obj.get("title")
                or resource_type_obj.get("type")
                or ""
            ).strip()
        keywords = metadata.get("keywords") if isinstance(metadata.get("keywords"), list) else []
        categories = [resource_type] if resource_type else []
        for keyword in keywords:
            k = str(keyword or "").strip()
            if not k:
                continue
            categories.append(k)
            if len(categories) >= 3:
                break

        published_raw = str(
            metadata.get("publication_date")
            or metadata.get("date")
            or row.get("created")
            or ""
        ).strip()
        published = published_raw[:10] if len(published_raw) >= 10 else published_raw

        paper_row = {
            "title": title,
            "authors": authors,
            "abstract": description,
            "url": url,
            "published": published,
            "categories": categories[:3],
            "doi": doi,
            "pdf_url": pdf_url or None,
            "source": "zenodo",
        }
        _annotate_access_metadata(paper_row)
        papers.append(paper_row)

    total = hits.get("total")
    if isinstance(total, dict):
        total = total.get("value")
    try:
        total = int(total) if total is not None else None
    except (TypeError, ValueError):
        total = None

    returned = len(papers)
    next_offset = start_offset + returned
    has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
    return {
        "papers": papers,
        "total": total,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "zenodo",
    }


@router.get("/search-openaire")
async def search_openaire(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search OpenAIRE publications."""
    page_size = max(1, min(max_results, 100))
    start_offset = max(0, offset)
    page = (start_offset // page_size) + 1
    params = {
        "keywords": query,
        "size": page_size,
        "page": page,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                OPENAIRE_API,
                params=params,
                headers={"User-Agent": "ResearchHub-AI/1.0"},
            )
            response.raise_for_status()
        root = ET.fromstring(response.text)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="OpenAIRE timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="OpenAIRE rate limit reached. Please retry shortly.")
        raise HTTPException(status_code=502, detail="OpenAIRE API upstream error.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="OpenAIRE API error.")
    except ET.ParseError:
        raise HTTPException(status_code=502, detail="OpenAIRE returned invalid XML.")

    papers: List[Dict[str, Any]] = []
    result_nodes = root.findall(".//result")
    for row in result_nodes:
        titles = _xml_text_values(row, "title", max_items=8)
        title = _first_nonempty(titles)
        if not title:
            continue

        creators = _xml_text_values(row, "creator", max_items=16)
        descriptions = _xml_text_values(row, "description", max_items=6)
        subjects = _xml_text_values(row, "subject", max_items=10)
        fulltexts = _xml_text_values(row, "fulltext", max_items=6)
        urls = _xml_text_values(row, "url", max_items=10)
        pids = (
            _xml_text_values(row, "pid", max_items=8)
            + _xml_text_values(row, "alternateidentifier", max_items=8)
            + _xml_text_values(row, "originalid", max_items=8)
        )
        date_values = (
            _xml_text_values(row, "dateofacceptance", max_items=4)
            + _xml_text_values(row, "relevantdate", max_items=4)
            + _xml_text_values(row, "dateofcollection", max_items=4)
        )
        source_values = _xml_text_values(row, "source", max_items=3)

        description = _first_nonempty([_strip_xml_html_tags(item) for item in descriptions], "No abstract available.")
        if not description:
            description = "No abstract available."

        doi = ""
        for token in pids + urls:
            doi_candidate = _looks_like_doi(token)
            if doi_candidate:
                doi = doi_candidate
                break

        full_text_url = _first_nonempty(fulltexts)
        first_url = _first_nonempty([item for item in urls if str(item).startswith("http")])
        url = full_text_url or first_url
        if not url and doi:
            url = f"https://doi.org/{doi}"

        published_raw = _first_nonempty(date_values)
        published = published_raw[:10] if len(published_raw) >= 10 else published_raw

        categories: List[str] = []
        for value in subjects:
            tag = str(value or "").strip()
            if not tag or tag in categories:
                continue
            categories.append(tag)
            if len(categories) >= 3:
                break

        paper_row: Dict[str, Any] = {
            "title": title,
            "authors": creators[:12],
            "abstract": description,
            "url": url,
            "published": published,
            "categories": categories,
            "doi": doi,
            "pdf_url": full_text_url if _is_pdf_url(full_text_url) else None,
            "publication_name": _first_nonempty(source_values),
            "source": "openaire",
        }
        _annotate_access_metadata(paper_row)
        papers.append(paper_row)

    total_value = root.findtext("./header/total", "")
    try:
        total = int(total_value) if str(total_value).strip() else None
    except (TypeError, ValueError):
        total = None

    returned = len(papers)
    next_offset = start_offset + returned
    has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
    return {
        "papers": papers,
        "total": total,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "openaire",
    }


@router.get("/search-figshare")
async def search_figshare(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search Figshare public records."""
    page_size = max(1, min(max_results, 100))
    start_offset = max(0, offset)
    page = (start_offset // page_size) + 1
    params = {
        "search_for": query,
        "page": page,
        "page_size": page_size,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                FIGSHARE_API,
                params=params,
                headers={"User-Agent": "ResearchHub-AI/1.0"},
            )
            response.raise_for_status()
        rows = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Figshare timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="Figshare rate limit reached. Please retry shortly.")
        raise HTTPException(status_code=502, detail="Figshare API upstream error.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Figshare API error.")

    if not isinstance(rows, list):
        rows = []

    papers = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        doi = _normalize_doi(str(row.get("doi") or ""))
        url = str(row.get("url_public_html") or "").strip()
        if not url:
            handle = str(row.get("handle") or "").strip()
            if handle:
                url = f"https://hdl.handle.net/{handle}"
        if not url and doi:
            url = f"https://doi.org/{doi}"
        published_raw = str(row.get("published_date") or "").strip()
        published = published_raw[:10] if len(published_raw) >= 10 else published_raw
        defined_type_name = str(row.get("defined_type_name") or "").strip()
        resource_title = str(row.get("resource_title") or "").strip()

        paper_row: Dict[str, Any] = {
            "title": title,
            "authors": [],
            "abstract": "No abstract available.",
            "url": url,
            "published": published,
            "categories": [item for item in [defined_type_name, resource_title] if item][:3],
            "doi": doi,
            "source": "figshare",
        }
        _annotate_access_metadata(paper_row)
        papers.append(paper_row)

    returned = len(papers)
    next_offset = start_offset + returned
    has_more = returned == page_size
    return {
        "papers": papers,
        "total": None,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "figshare",
    }


@router.get("/search-osf")
async def search_osf(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search OSF preprints."""
    page_size = max(1, min(max_results, 100))
    start_offset = max(0, offset)
    page = (start_offset // page_size) + 1
    params = {
        "filter[title]": query,
        "page[size]": page_size,
        "page": page,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                OSF_PREPRINT_API,
                params=params,
                headers={"User-Agent": "ResearchHub-AI/1.0"},
            )
            response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="OSF timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="OSF rate limit reached. Please retry shortly.")
        raise HTTPException(status_code=502, detail="OSF API upstream error.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="OSF API error.")

    rows = data.get("data") if isinstance(data, dict) else []
    if not isinstance(rows, list):
        rows = []

    papers = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        attrs = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
        links = row.get("links") if isinstance(row.get("links"), dict) else {}
        title = str(attrs.get("title") or "").strip()
        if not title:
            continue
        doi = _normalize_doi(str(attrs.get("doi") or ""))
        if not doi:
            doi = _looks_like_doi(str(links.get("preprint_doi") or ""))
        url = str(links.get("html") or links.get("preprint_doi") or links.get("self") or "").strip()
        if not url and doi:
            url = f"https://doi.org/{doi}"
        description = _strip_xml_html_tags(attrs.get("description") or "")
        if not description:
            description = "No abstract available."
        published_raw = str(attrs.get("date_published") or attrs.get("original_publication_date") or "").strip()
        published = published_raw[:10] if len(published_raw) >= 10 else published_raw

        subject_tags: List[str] = []
        subjects = attrs.get("subjects")
        if isinstance(subjects, list):
            for branch in subjects:
                if not isinstance(branch, list):
                    continue
                for subject in branch:
                    if not isinstance(subject, dict):
                        continue
                    text = str(subject.get("text") or "").strip()
                    if not text or text in subject_tags:
                        continue
                    subject_tags.append(text)
                    if len(subject_tags) >= 3:
                        break
                if len(subject_tags) >= 3:
                    break

        paper_row: Dict[str, Any] = {
            "title": title,
            "authors": [],
            "abstract": description,
            "url": url,
            "published": published,
            "categories": subject_tags,
            "doi": doi,
            "source": "osf",
        }
        _annotate_access_metadata(paper_row)
        papers.append(paper_row)

    returned = len(papers)
    next_offset = start_offset + returned
    has_more = bool((data.get("links") or {}).get("next")) if isinstance(data, dict) else (returned == page_size)
    return {
        "papers": papers,
        "total": None,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "osf",
    }


@router.get("/search-dryad")
async def search_dryad(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search Dryad datasets/publications."""
    page_size = max(1, min(max_results, 100))
    start_offset = max(0, offset)
    page = (start_offset // page_size) + 1
    params = {
        "query": query,
        "page[size]": page_size,
        "page[number]": page,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                DRYAD_API,
                params=params,
                headers={"User-Agent": "ResearchHub-AI/1.0"},
            )
            response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Dryad timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="Dryad rate limit reached. Please retry shortly.")
        raise HTTPException(status_code=502, detail="Dryad API upstream error.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Dryad API error.")

    embedded = data.get("_embedded") if isinstance(data, dict) else {}
    if not isinstance(embedded, dict):
        embedded = {}
    rows = embedded.get("stash:datasets")
    if not isinstance(rows, list):
        rows = []

    papers = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        doi = _normalize_doi(str(row.get("identifier") or ""))
        url = f"https://doi.org/{doi}" if doi else ""
        if not url:
            links = row.get("_links") if isinstance(row.get("_links"), dict) else {}
            self_link = links.get("self") if isinstance(links.get("self"), dict) else {}
            href = str(self_link.get("href") or "").strip()
            if href.startswith("/"):
                url = f"https://datadryad.org{href}"
            else:
                url = href
        description = _strip_xml_html_tags(row.get("abstract") or "")
        if not description:
            description = "No abstract available."
        published_raw = str(row.get("publicationDate") or "").strip()
        published = published_raw[:10] if len(published_raw) >= 10 else published_raw

        authors = []
        for author in row.get("authors") or []:
            if not isinstance(author, dict):
                continue
            first = str(author.get("firstName") or "").strip()
            last = str(author.get("lastName") or "").strip()
            full_name = f"{first} {last}".strip() or str(author.get("name") or "").strip()
            if not full_name:
                continue
            authors.append(full_name)
            if len(authors) >= 12:
                break

        categories = []
        for keyword in row.get("keywords") or []:
            value = str(keyword or "").strip()
            if not value or value in categories:
                continue
            categories.append(value)
            if len(categories) >= 3:
                break

        paper_row: Dict[str, Any] = {
            "title": title,
            "authors": authors,
            "abstract": description,
            "url": url,
            "published": published,
            "categories": categories,
            "doi": doi,
            "source": "dryad",
        }
        _annotate_access_metadata(paper_row)
        papers.append(paper_row)

    total = data.get("total") if isinstance(data, dict) else None
    try:
        total = int(total) if total is not None else None
    except (TypeError, ValueError):
        total = None

    returned = len(papers)
    next_offset = start_offset + returned
    has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
    return {
        "papers": papers,
        "total": total,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "dryad",
    }


@router.get("/search-inspire")
async def search_inspire(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search INSPIRE-HEP literature API."""
    page_size = max(1, min(max_results, 100))
    start_offset = max(0, offset)
    page = (start_offset // page_size) + 1
    params = {
        "q": query,
        "size": page_size,
        "page": page,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                INSPIRE_HEP_API,
                params=params,
                headers={"User-Agent": "ResearchHub-AI/1.0"},
            )
            response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="INSPIRE-HEP timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="INSPIRE-HEP rate limit reached. Please retry shortly.")
        raise HTTPException(status_code=502, detail="INSPIRE-HEP API upstream error.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="INSPIRE-HEP API error.")

    hits = data.get("hits") if isinstance(data, dict) else {}
    if not isinstance(hits, dict):
        hits = {}
    rows = hits.get("hits")
    if not isinstance(rows, list):
        rows = []

    papers = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        titles = metadata.get("titles") if isinstance(metadata.get("titles"), list) else []
        first_title = titles[0] if titles and isinstance(titles[0], dict) else {}
        title = str(first_title.get("title") or "").strip()
        if not title:
            continue

        abstracts = metadata.get("abstracts") if isinstance(metadata.get("abstracts"), list) else []
        first_abstract = abstracts[0] if abstracts and isinstance(abstracts[0], dict) else {}
        description = _strip_xml_html_tags(first_abstract.get("value") or "")
        if not description:
            description = "No abstract available."

        authors = []
        for author in metadata.get("authors") or []:
            if not isinstance(author, dict):
                continue
            name = str(author.get("full_name") or "").strip()
            if not name:
                continue
            authors.append(name)
            if len(authors) >= 12:
                break

        doi = ""
        for item in metadata.get("dois") or []:
            if not isinstance(item, dict):
                continue
            doi = _normalize_doi(str(item.get("value") or ""))
            if doi:
                break

        published_raw = str(metadata.get("earliest_date") or metadata.get("preprint_date") or "").strip()
        published = published_raw[:10] if len(published_raw) >= 10 else published_raw
        control_number = metadata.get("control_number") or row.get("id")
        url = f"https://inspirehep.net/literature/{control_number}" if control_number else ""
        if not url and doi:
            url = f"https://doi.org/{doi}"

        categories = []
        for cat in metadata.get("inspire_categories") or []:
            if not isinstance(cat, dict):
                continue
            term = str(cat.get("term") or "").strip()
            if not term or term in categories:
                continue
            categories.append(term)
            if len(categories) >= 3:
                break

        paper_row: Dict[str, Any] = {
            "title": title,
            "authors": authors,
            "abstract": description,
            "url": url,
            "published": published,
            "categories": categories,
            "doi": doi,
            "source": "inspire",
        }
        _annotate_access_metadata(paper_row)
        papers.append(paper_row)

    total = hits.get("total")
    if isinstance(total, dict):
        total = total.get("value")
    try:
        total = int(total) if total is not None else None
    except (TypeError, ValueError):
        total = None

    returned = len(papers)
    next_offset = start_offset + returned
    has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
    return {
        "papers": papers,
        "total": total,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "inspire",
    }



# ---------------------------------------------------------------------------
# Global merged search (query all sources and merge)
# ---------------------------------------------------------------------------

@router.get("/search-global")
async def search_global(
    query: str,
    max_results: int = 60,
    offset: int = 0,
    search_mode: str = "balanced",
    track_history: bool = True,
    current_user: User = Depends(get_current_user),
):
    """Search all sources together and return merged, de-duplicated results."""
    started_at = time.perf_counter()
    _GLOBAL_SEARCH_METRICS["requests_total"] = int(_GLOBAL_SEARCH_METRICS.get("requests_total", 0)) + 1
    resolved_mode = _normalize_search_mode(search_mode)
    max_cap = int(GLOBAL_SEARCH_MAX_RESULTS_BY_MODE.get(resolved_mode, 140))
    page_size = max(10, min(max_results, max_cap))
    start_offset = max(0, offset)
    cache_key = _global_cache_key(
        query=query,
        max_results=page_size,
        offset=start_offset,
        search_mode=resolved_mode,
    )
    cached = _global_cache_get(cache_key)
    if cached:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        _GLOBAL_SEARCH_METRICS["cache_hits_total"] = int(_GLOBAL_SEARCH_METRICS.get("cache_hits_total", 0)) + 1
        _GLOBAL_SEARCH_METRICS["last_duration_ms"] = elapsed_ms
        _GLOBAL_SEARCH_METRICS["last_cached"] = True
        _GLOBAL_SEARCH_METRICS["last_checked_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        _log_search_event(
            "search_global_cache_hit",
            user_id=current_user.id,
            search_mode=resolved_mode,
            query_len=len(query.strip()),
            offset=start_offset,
            max_results=page_size,
            duration_ms=elapsed_ms,
            returned=int(cached.get("returned") or 0),
        )
        if track_history:
            _record_search_history(
                user_id=current_user.id,
                query=query,
                result_count=int(cached.get("returned") or 0),
                max_results=page_size,
                offset=start_offset,
                source_status=cached.get("source_status") or {},
                cache_hit=True,
            )
        return cached

    source_order = list(GLOBAL_SEARCH_SOURCE_PRESETS.get(resolved_mode, GLOBAL_SEARCH_SOURCE_PRESETS["balanced"]))
    if resolved_mode == "fast":
        per_source_limit = max(6, min(20, (page_size // max(1, len(source_order))) + 6))
    elif resolved_mode == "deep":
        per_source_limit = max(10, min(40, (page_size // max(1, len(source_order))) + 12))
    else:
        per_source_limit = max(8, min(30, (page_size // max(1, len(source_order))) + 8))
    source_concurrency = int(GLOBAL_SOURCE_CONCURRENCY_BY_MODE.get(resolved_mode, GLOBAL_SOURCE_CONCURRENCY))
    source_semaphore = asyncio.Semaphore(max(3, source_concurrency))

    async def _run_source(source_name: str):
        try:
            if source_name == "arxiv":
                data = await search_papers(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    category="all",
                    sort_by="relevance",
                    current_user=current_user,
                )
            elif source_name == "semantic":
                data = await search_semantic(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    allow_fallback_arxiv=False,
                    current_user=current_user,
                )
            elif source_name == "openalex":
                data = await search_openalex(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "europepmc":
                data = await search_europepmc(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "pubmed":
                data = await search_pubmed(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "doaj":
                data = await search_doaj(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "openaire":
                data = await search_openaire(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "figshare":
                data = await search_figshare(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "osf":
                data = await search_osf(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "dryad":
                data = await search_dryad(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "inspire":
                data = await search_inspire(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "dblp":
                data = await search_dblp(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "zenodo":
                data = await search_zenodo(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "datacite":
                data = await search_datacite(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "crossref":
                data = await search_crossref(
                    query=query,
                    max_results=min(per_source_limit, 50),
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "hal":
                data = await search_hal(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "biorxiv":
                data = await search_biorxiv(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "medrxiv":
                data = await search_medrxiv(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "plos":
                data = await search_plos(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "elife":
                data = await search_elife(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "springer":
                data = await search_springer(
                    query=query,
                    max_results=min(per_source_limit, 25),
                    offset=start_offset,
                    current_user=current_user,
                )
            elif source_name == "nasa":
                data = await search_nasa_ads(
                    query=query,
                    max_results=per_source_limit,
                    offset=start_offset,
                    current_user=current_user,
                )
            else:
                data = {"papers": []}
            return source_name, data, None
        except HTTPException as exc:
            return source_name, None, str(exc.detail)
        except Exception as exc:
            logging.exception("Global search source failed: %s", source_name)
            return source_name, None, str(exc)

    async def _run_with_cap(name: str):
        base_timeout = float(GLOBAL_SOURCE_TIMEOUT_OVERRIDES.get(name, GLOBAL_SOURCE_TIMEOUT_SECONDS))
        timeout_factor = float(GLOBAL_SOURCE_TIMEOUT_FACTOR_BY_MODE.get(resolved_mode, 1.0))
        timeout_budget = max(2.5, base_timeout * timeout_factor)
        try:
            async with source_semaphore:
                return await asyncio.wait_for(_run_source(name), timeout=timeout_budget)
        except asyncio.TimeoutError:
            return name, None, "timeout"

    task_map = {asyncio.create_task(_run_with_cap(name)): name for name in source_order}
    source_results = []
    completed_sources = set()
    collected_raw = 0
    successful_sources = 0
    fast_path_reached = False
    if resolved_mode == "fast":
        fast_path_target = max(18, min(page_size + 8, 52))
    elif resolved_mode == "deep":
        fast_path_target = max(36, min(page_size + 18, 110))
    else:
        fast_path_target = max(26, min(page_size + 10, 72))

    try:
        wait_budget = float(GLOBAL_SEARCH_WAIT_BY_MODE.get(resolved_mode, GLOBAL_SEARCH_WAIT_SECONDS))
        for finished in asyncio.as_completed(list(task_map.keys()), timeout=wait_budget):
            result = await finished
            source_results.append(result)
            source_name, data, error = result
            completed_sources.add(source_name)
            if error:
                continue
            papers = (data or {}).get("papers") or []
            if papers:
                successful_sources += 1
                collected_raw += len(papers)
            # Fast-path: once we have enough material from multiple sources,
            # avoid waiting for the slowest providers.
            if successful_sources >= 3 and collected_raw >= fast_path_target:
                fast_path_reached = True
                break
    except asyncio.TimeoutError:
        pass

    for task, source_name in task_map.items():
        if source_name in completed_sources:
            continue
        if task.done():
            try:
                source_results.append(task.result())
            except Exception as exc:
                source_results.append((source_name, None, str(exc)))
        else:
            task.cancel()
            pending_reason = "skipped_fast_path" if fast_path_reached else "global_timeout"
            source_results.append((source_name, None, pending_reason))

    seen_keys = set()
    merged_papers: List[Dict[str, Any]] = []
    source_counts: Dict[str, int] = {}
    source_status: Dict[str, Dict[str, Any]] = {}
    failures: List[str] = []
    notices: List[str] = []

    for source_name, data, error in source_results:
        if error:
            source_counts[source_name] = 0
            if str(error) == "skipped_fast_path":
                source_status[source_name] = {
                    "status": "skipped",
                    "count": 0,
                    "detail": "Deferred after enough merged results.",
                }
                continue
            failures.append(f"{source_name}: {str(error)[:140]}")
            source_status[source_name] = {
                "status": "timeout" if "timeout" in str(error).lower() else "error",
                "count": 0,
                "detail": str(error)[:140],
            }
            continue

        papers = (data or {}).get("papers") or []
        source_counts[source_name] = len(papers)
        source_status[source_name] = {
            "status": "ok",
            "count": len(papers),
        }
        notice = (data or {}).get("notice")
        if notice:
            notices.append(str(notice))
            source_status[source_name]["status"] = "warning"
            source_status[source_name]["detail"] = str(notice)[:140]

        for paper in papers:
            key = _paper_dedupe_key(paper)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged_papers.append(paper)

    # Recovery pass: if the parallel run produced zero papers (for example during
    # transient upstream latency spikes), retry a few high-yield sources directly.
    if not merged_papers:
        async def _run_recovery(source_name: str) -> Tuple[str, Optional[Dict[str, Any]], Optional[str]]:
            try:
                if source_name == "openalex":
                    payload = await asyncio.wait_for(
                        search_openalex(
                            query=query,
                            max_results=min(page_size, 30),
                            offset=start_offset,
                            current_user=current_user,
                        ),
                        timeout=4.5,
                    )
                    return source_name, payload, None
                if source_name == "arxiv":
                    payload = await asyncio.wait_for(
                        search_papers(
                            query=query,
                            max_results=min(page_size, 30),
                            offset=start_offset,
                            category="all",
                            sort_by="relevance",
                            current_user=current_user,
                        ),
                        timeout=4.5,
                    )
                    return source_name, payload, None
                if source_name == "europepmc":
                    payload = await asyncio.wait_for(
                        search_europepmc(
                            query=query,
                            max_results=min(page_size, 30),
                            offset=start_offset,
                            current_user=current_user,
                        ),
                        timeout=4.5,
                    )
                    return source_name, payload, None
                return source_name, None, "unsupported"
            except HTTPException as exc:
                return source_name, None, str(exc.detail)
            except Exception:
                return source_name, None, "Recovery pass failed."

        recovery_results = await asyncio.gather(
            *[_run_recovery(name) for name in ("openalex", "arxiv", "europepmc")],
            return_exceptions=False,
        )

        for source_name, recovered, recovery_error in recovery_results:
            if recovery_error:
                source_counts[source_name] = 0
                source_status[source_name] = {
                    "status": "error",
                    "count": 0,
                    "detail": f"Recovery pass failed: {str(recovery_error)[:120]}",
                }
                continue

            recovered_papers = (recovered or {}).get("papers") or []
            source_counts[source_name] = max(source_counts.get(source_name, 0), len(recovered_papers))
            if recovered_papers:
                source_status[source_name] = {
                    "status": "ok",
                    "count": len(recovered_papers),
                    "detail": "Recovered in fallback pass.",
                }
                for paper in recovered_papers:
                    key = _paper_dedupe_key(paper)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    merged_papers.append(paper)
            else:
                source_status[source_name] = {
                    "status": "warning",
                    "count": 0,
                    "detail": "Recovery pass returned no papers.",
                }

    for name in source_order:
        if name not in source_status:
            source_status[name] = {
                "status": "skipped" if fast_path_reached else "error",
                "count": 0,
                "detail": "Deferred after enough merged results." if fast_path_reached else "no response",
            }
            source_counts[name] = source_counts.get(name, 0)

    # Enrich missing PDFs via Unpaywall for a small bounded set only.
    max_unpaywall_lookups = int(
        GLOBAL_UNPAYWALL_MAX_LOOKUPS_BY_MODE.get(resolved_mode, GLOBAL_UNPAYWALL_MAX_LOOKUPS)
    )
    if start_offset > 0:
        # Keep "load more" fast and avoid repeated DOI enrichment costs on later pages.
        max_unpaywall_lookups = 0
    enrich_candidates = [
        paper
        for paper in merged_papers
        if (paper.get("doi") and not _has_pdf(paper))
    ][:max_unpaywall_lookups]

    async def _enrich_pdf(paper: Dict[str, Any]) -> None:
        try:
            pdf_url = await asyncio.wait_for(
                _fetch_unpaywall_pdf(str(paper.get("doi") or "")),
                timeout=GLOBAL_UNPAYWALL_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            pdf_url = None
        if not pdf_url:
            return
        paper["pdf_url"] = pdf_url
        if not paper.get("url"):
            paper["url"] = pdf_url

    if enrich_candidates:
        await asyncio.gather(*[_enrich_pdf(p) for p in enrich_candidates], return_exceptions=True)

    for paper in merged_papers:
        _annotate_access_metadata(paper)

    merged_papers.sort(
        key=lambda p: (
            _paper_year_sort_value(p),
            1 if _has_pdf(p) else 0,
            1 if (p.get("abstract") and "no abstract" not in str(p.get("abstract")).lower()) else 0,
        ),
        reverse=True,
    )

    has_more = len(merged_papers) > page_size
    merged_page = merged_papers[:page_size]

    # Silence noisy warnings: only surface notice when no results at all.
    notice = None
    if not merged_page and (failures or notices):
        notice_parts: List[str] = []
        if failures:
            notice_parts.append("Sources unavailable: " + "; ".join(failures))
        if notices:
            notice_parts.extend(notices)
        notice = " ".join(notice_parts) if notice_parts else None

    response_payload = {
        "papers": merged_page,
        "total": None,
        "returned": len(merged_page),
        "offset": start_offset,
        "next_offset": start_offset + len(merged_page),
        "has_more": has_more,
        "source": "global_merged",
        "search_mode": resolved_mode,
        "sources_queried": source_order,
        "source_counts": source_counts,
        "source_status": source_status,
        "notice": notice,
        "cache_hit": False,
        "duration_ms": 0,
    }

    timeout_count = sum(1 for item in source_status.values() if str(item.get("status")) == "timeout")
    error_count = sum(1 for item in source_status.values() if str(item.get("status")) == "error")
    partial = any(str(item.get("status")) in {"timeout", "error", "warning"} for item in source_status.values())
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    response_payload["duration_ms"] = elapsed_ms

    _GLOBAL_SEARCH_METRICS["timeouts_total"] = int(_GLOBAL_SEARCH_METRICS.get("timeouts_total", 0)) + timeout_count
    _GLOBAL_SEARCH_METRICS["errors_total"] = int(_GLOBAL_SEARCH_METRICS.get("errors_total", 0)) + error_count
    if partial:
        _GLOBAL_SEARCH_METRICS["partial_results_total"] = int(_GLOBAL_SEARCH_METRICS.get("partial_results_total", 0)) + 1
    _GLOBAL_SEARCH_METRICS["last_duration_ms"] = elapsed_ms
    _GLOBAL_SEARCH_METRICS["last_cached"] = False
    _GLOBAL_SEARCH_METRICS["last_source_status"] = source_status
    _GLOBAL_SEARCH_METRICS["last_checked_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    _log_search_event(
        "search_global_complete",
        user_id=current_user.id,
        search_mode=resolved_mode,
        query_len=len(query.strip()),
        offset=start_offset,
        max_results=page_size,
        duration_ms=elapsed_ms,
        returned=len(merged_page),
        timeouts=timeout_count,
        errors=error_count,
        partial=partial,
        cache_hit=False,
    )

    if track_history:
        _record_search_history(
            user_id=current_user.id,
            query=query,
            result_count=len(merged_page),
            max_results=page_size,
            offset=start_offset,
            source_status=source_status,
            cache_hit=False,
        )

    _global_cache_put(cache_key, response_payload)
    return response_payload


@router.get("/search-history")
def get_search_history(
    limit: int = 25,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    page_size = max(1, min(limit, 200))
    rows = (
        db.query(SearchHistory)
        .filter(SearchHistory.user_id == current_user.id)
        .order_by(SearchHistory.created_at.desc())
        .limit(page_size)
        .all()
    )
    items: List[Dict[str, Any]] = []
    for row in rows:
        filters: Dict[str, Any] = {}
        if row.filters_json:
            try:
                parsed = json.loads(row.filters_json)
                if isinstance(parsed, dict):
                    filters = parsed
            except Exception:
                filters = {}
        items.append(
            {
                "id": row.id,
                "query": row.query,
                "source": row.source,
                "result_count": row.result_count,
                "created_at": (
                    row.created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                    if row.created_at
                    else None
                ),
                "filters": filters,
            }
        )
    return {"items": items, "count": len(items)}


@router.get("/search-history/insights")
def get_search_history_insights(
    limit: int = 120,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    size = max(10, min(limit, 500))
    rows = (
        db.query(SearchHistory)
        .filter(SearchHistory.user_id == current_user.id)
        .order_by(SearchHistory.created_at.desc())
        .limit(size)
        .all()
    )

    query_counts: Dict[str, int] = {}
    weighted_counts: Dict[str, float] = {}
    display_queries: Dict[str, str] = {}
    source_counts: Dict[str, int] = {}
    total_results = 0

    for row in rows:
        query_text = str(row.query or "").strip()
        if not query_text:
            continue
        key = query_text.lower()
        query_counts[key] = query_counts.get(key, 0) + 1
        weighted_counts[key] = weighted_counts.get(key, 0.0) + max(0, int(row.result_count or 0)) / 10.0 + 1.0
        if key not in display_queries:
            display_queries[key] = query_text
        src = str(row.source or "unknown").lower()
        source_counts[src] = source_counts.get(src, 0) + 1
        total_results += max(0, int(row.result_count or 0))

    top_queries = sorted(
        (
            {
                "query": query,
                "display_query": display_queries.get(query, query),
                "count": query_counts[query],
                "weight": round(weighted_counts.get(query, 0.0), 2),
            }
            for query in query_counts.keys()
        ),
        key=lambda item: (item["weight"], item["count"]),
        reverse=True,
    )[:12]

    avg_results = round((total_results / len(rows)), 2) if rows else 0.0
    last_at = (
        rows[0].created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if rows and rows[0].created_at
        else None
    )
    return {
        "count": len(rows),
        "avg_result_count": avg_results,
        "top_queries": top_queries,
        "source_counts": source_counts,
        "last_activity_at": last_at,
    }


@router.delete("/search-history")
def delete_search_history(
    item_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(SearchHistory).filter(SearchHistory.user_id == current_user.id)
    if item_id is not None:
        row = query.filter(SearchHistory.id == item_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Search history item not found.")
        db.delete(row)
        db.commit()
        return {"message": "Search history item deleted."}

    deleted = query.delete(synchronize_session=False)
    db.commit()
    return {"message": "Search history cleared.", "deleted": int(deleted or 0)}


@router.get("/metrics")
async def papers_metrics(current_user: User = Depends(get_current_user)):
    """Expose lightweight runtime metrics for papers search reliability."""
    now = time.time()
    live_cache_items = sum(1 for item in _GLOBAL_SEARCH_CACHE.values() if now <= float(item.get("expires_at", 0)))
    return {
        "global_search": {
            **_GLOBAL_SEARCH_METRICS,
            "cache_live_items": live_cache_items,
            "cache_capacity": GLOBAL_SEARCH_CACHE_MAX_ITEMS,
            "cache_ttl_seconds": GLOBAL_SEARCH_CACHE_TTL_SECONDS,
        }
    }

# ---------------------------------------------------------------------------
# Springer Nature search  (Meta API — broad science/engineering coverage)
# ---------------------------------------------------------------------------

@router.get("/search-springer")
async def search_springer(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search Springer Nature Meta API (~12M articles, science & engineering)."""
    springer_key = _get_springer_key()
    if not springer_key:
        raise HTTPException(status_code=503, detail="Springer Nature API key not configured.")

    # Springer Meta API rejects larger page sizes on some plans (often above 25).
    page_size = max(1, min(max_results, 25))
    start_offset = max(0, offset)
    params = {
        "q": query,
        "p": page_size,
        "s": start_offset + 1,
        "api_key": springer_key,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            for attempt in range(2):
                try:
                    response = await client.get(SPRINGER_META_API, params=params)
                    response.raise_for_status()
                    break
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (401, 403):
                        # Retry once using key read directly from backend/.env if different.
                        file_key = _get_springer_key()
                        if file_key and file_key != springer_key:
                            params["api_key"] = file_key
                            response = await client.get(SPRINGER_META_API, params=params)
                            response.raise_for_status()
                            os.environ["SPRINGER_META_KEY"] = file_key
                            break
                        raise
                    if attempt == 1:
                        raise
                    await client.aclose()
                    async with httpx.AsyncClient(timeout=20) as client:
                        continue
        try:
            data = response.json()
        except ValueError:
            raise HTTPException(status_code=502, detail=f"Springer returned non-JSON response: {response.text[:300]}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Springer API timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise HTTPException(status_code=401, detail="Springer API key invalid.")
        if e.response.status_code == 403:
            body = (e.response.text or "").lower()
            if "premium feature" in body or "restricted" in body:
                raise HTTPException(
                    status_code=403,
                    detail="Springer plan limit reached for requested page size. Use 25 results or fewer.",
                )
            raise HTTPException(status_code=403, detail="Springer access forbidden by upstream service.")
        raise HTTPException(status_code=502, detail="Springer API upstream error.")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="Springer API error.")

    papers = []
    try:
        for item in data.get("records", []):
            creators = item.get("creators") or []
            authors = [c.get("creator", "") for c in creators]

            abstract = item.get("abstract") or "No abstract available."
            published = (item.get("publicationDate") or item.get("onlineDate") or "")[:10]

            # URL — prefer DOI. Springer may return `url` as a list, dict, or plain string;
            # handle all shapes defensively to avoid runtime 500s when upstream data
            # shape changes.
            doi = item.get("doi") or ""
            raw_url = item.get("url")
            url_val = ""
            if doi:
                url_val = f"https://doi.org/{doi}"
            else:
                if isinstance(raw_url, list) and raw_url:
                    first = raw_url[0]
                    if isinstance(first, dict):
                        url_val = first.get("value", "") or ""
                    else:
                        url_val = str(first)
                elif isinstance(raw_url, dict):
                    url_val = raw_url.get("value", "") or ""
                elif isinstance(raw_url, str):
                    url_val = raw_url
                else:
                    url_val = ""
            url = url_val

            # `subjects` from Springer can be a list of dicts, a plain string, or
            # occasionally a dict — handle all shapes defensively to avoid 500s.
            raw_subjects = item.get("subjects") or []
            subjects = []
            if isinstance(raw_subjects, list):
                subjects = [s.get("term", "") if isinstance(s, dict) else str(s) for s in raw_subjects]
            elif isinstance(raw_subjects, dict):
                subjects = [raw_subjects.get("term", "")]
            elif isinstance(raw_subjects, str):
                subjects = [raw_subjects]
            else:
                subjects = []

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
                "publication_name": pub_name or "",
                "source": "springer",
            })
    except Exception as e:
        logging.exception("Springer: error processing records")
        raise HTTPException(status_code=502, detail=f"Springer processing error: {str(e)[:200]}")

    total = None
    try:
        results_meta = data.get("result") or []
        if results_meta and isinstance(results_meta, list):
            total_raw = results_meta[0].get("total")
            if total_raw is not None:
                total = int(total_raw)
    except (ValueError, TypeError, AttributeError, IndexError):
        total = None

    returned = len(papers)
    next_offset = start_offset + returned
    has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
    return {
        "papers": papers,
        "total": total,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "springer",
    }


# ---------------------------------------------------------------------------
# NASA ADS search  (astrophysics, astronomy, physics, geoscience)
# ---------------------------------------------------------------------------

# Development-only debug handler to verify the running process sees the token.
# Do NOT enable in production environments.
if os.getenv("APP_ENV", "development") == "development":
    @router.get('/debug/nasa-token')
    def _debug_nasa_token():
        try:
            t = (os.getenv("NASA_ADS_TOKEN") or "")
            masked = f"{t[:4]}...{t[-4:]}" if t else "(not-set)"
        except Exception:
            masked = "(error)"
        return {"nasa_ads_token_masked": masked}



@router.get("/search-nasa")
async def search_nasa_ads(
    query: str,
    max_results: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """Search NASA Astrophysics Data System — resilient token lookup + retry.

    Behavior changes:
    - Read `NASA_ADS_TOKEN` from process env first; if missing or the ADS API
      rejects the token (401/403), attempt to read the token directly from
      `backend/.env` and retry once. If the `.env` token works, inject it into
      `os.environ` so subsequent requests use the correct value.
    """
    token = _get_nasa_token()

    if not token:
        raise HTTPException(status_code=503, detail="NASA ADS token not configured.")

    page_size = max(1, min(max_results, 100))
    start_offset = max(0, offset)
    params = {
        "q": query,
        "fl": "title,author,abstract,year,doi,bibcode,doctype",
        "rows": page_size,
        "start": start_offset,
        "sort": "score desc",
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                NASA_ADS_API,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        logging.warning("NASA ADS timeout url=%s", NASA_ADS_API)
        raise HTTPException(status_code=504, detail="NASA ADS timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        # If ADS rejected the token, attempt one retry using the token from
        # `backend/.env` (if different). This often fixes cases where process
        # env and .env drifted in local dev.
        if e.response.status_code in (401, 403):
            file_token = _get_nasa_token()
            if file_token and file_token != token:
                # retry once with token read directly from .env
                try:
                    async with httpx.AsyncClient(timeout=20) as client:
                        response = await client.get(
                            NASA_ADS_API,
                            params=params,
                            headers={"Authorization": f"Bearer {file_token}"},
                        )
                        response.raise_for_status()
                    os.environ['NASA_ADS_TOKEN'] = file_token
                    data = response.json()
                except Exception:
                    raise HTTPException(status_code=401, detail="NASA ADS token invalid.")
            else:
                raise HTTPException(status_code=401, detail="NASA ADS token invalid.")
        else:
            # Log status code and a truncated body snippet to help diagnostics (no secrets)
            try:
                body = e.response.text[:200].replace("\n", " ")
            except Exception:
                body = "(unavailable)"
            logging.warning("NASA ADS http_status=%s url=%s body=%s", e.response.status_code, NASA_ADS_API, body)
            raise HTTPException(status_code=502, detail="NASA ADS upstream error.")
    except httpx.HTTPError as e:
        logging.warning("NASA ADS http_error url=%s err=%s", NASA_ADS_API, str(e)[:200])
        raise HTTPException(status_code=502, detail="NASA ADS error.")

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

    total = (data.get("response") or {}).get("numFound")
    returned = len(papers)
    next_offset = start_offset + returned
    has_more = (next_offset < total) if isinstance(total, int) else (returned == page_size)
    return {
        "papers": papers,
        "total": total,
        "returned": returned,
        "offset": start_offset,
        "next_offset": next_offset,
        "has_more": has_more,
        "source": "nasa_ads",
    }


@router.get("/source-health")
async def source_health(current_user: User = Depends(get_current_user)):
    """Run lightweight live diagnostics for key-based sources."""
    sources: Dict[str, Any] = {}

    springer_key = _get_springer_key()
    springer_info: Dict[str, Any] = {
        "configured": bool(springer_key),
        "reachable": False,
        "status": "not_configured" if not springer_key else "checking",
        "detail": "API key missing" if not springer_key else "",
    }
    if springer_key:
        started = datetime.now(timezone.utc)
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.get(
                    SPRINGER_META_API,
                    params={"q": "machine learning", "p": 1, "s": 1, "api_key": springer_key},
                )
            elapsed = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            if response.status_code == 200:
                springer_info.update({
                    "reachable": True,
                    "status": "ok",
                    "detail": "Access verified",
                    "latency_ms": elapsed,
                })
            elif response.status_code in (401, 403):
                springer_info.update({
                    "status": "auth_error",
                    "detail": "API key rejected",
                    "latency_ms": elapsed,
                })
            else:
                springer_info.update({
                    "status": "upstream_error",
                    "detail": f"HTTP {response.status_code}",
                    "latency_ms": elapsed,
                })
        except httpx.TimeoutException:
            springer_info.update({"status": "timeout", "detail": "Request timed out"})
        except httpx.HTTPError:
            springer_info.update({"status": "network_error", "detail": "Network/API error"})
    sources["springer"] = springer_info

    nasa_token = _get_nasa_token()
    nasa_info: Dict[str, Any] = {
        "configured": bool(nasa_token),
        "reachable": False,
        "status": "not_configured" if not nasa_token else "checking",
        "detail": "Token missing" if not nasa_token else "",
    }
    if nasa_token:
        started = datetime.now(timezone.utc)
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.get(
                    NASA_ADS_API,
                    params={"q": "machine learning", "fl": "title", "rows": 1, "start": 0, "sort": "score desc"},
                    headers={"Authorization": f"Bearer {nasa_token}"},
                )
            elapsed = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            if response.status_code == 200:
                nasa_info.update({
                    "reachable": True,
                    "status": "ok",
                    "detail": "Access verified",
                    "latency_ms": elapsed,
                })
            elif response.status_code in (401, 403):
                nasa_info.update({
                    "status": "auth_error",
                    "detail": "Token rejected",
                    "latency_ms": elapsed,
                })
            else:
                nasa_info.update({
                    "status": "upstream_error",
                    "detail": f"HTTP {response.status_code}",
                    "latency_ms": elapsed,
                })
        except httpx.TimeoutException:
            nasa_info.update({"status": "timeout", "detail": "Request timed out"})
        except httpx.HTTPError:
            nasa_info.update({"status": "network_error", "detail": "Network/API error"})
    sources["nasa"] = nasa_info

    groq_key = _get_groq_key()
    groq_info: Dict[str, Any] = {
        "configured": bool(groq_key),
        "reachable": False,
        "status": "not_configured" if not groq_key else "checking",
        "detail": "API key missing" if not groq_key else "",
    }
    if groq_key:
        started = datetime.now(timezone.utc)
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {groq_key}"},
                )
            elapsed = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            if response.status_code == 200:
                groq_info.update({
                    "reachable": True,
                    "status": "ok",
                    "detail": "Access verified",
                    "latency_ms": elapsed,
                })
            elif response.status_code in (401, 403):
                groq_info.update({
                    "status": "auth_error",
                    "detail": "API key rejected",
                    "latency_ms": elapsed,
                })
            else:
                groq_info.update({
                    "status": "upstream_error",
                    "detail": f"HTTP {response.status_code}",
                    "latency_ms": elapsed,
                })
        except httpx.TimeoutException:
            groq_info.update({"status": "timeout", "detail": "Request timed out"})
        except httpx.HTTPError:
            groq_info.update({"status": "network_error", "detail": "Network/API error"})
    sources["groq"] = groq_info

    europepmc_info: Dict[str, Any] = {
        "configured": True,  # public open API
        "reachable": False,
        "status": "checking",
        "detail": "",
    }
    started = datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(
                EUROPE_PMC_API,
                params={
                    "query": "machine learning",
                    "format": "json",
                    "pageSize": 1,
                    "page": 1,
                },
                headers={"User-Agent": "ResearchHub-AI/1.0"},
            )
        elapsed = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        if response.status_code == 200:
            europepmc_info.update({
                "reachable": True,
                "status": "ok",
                "detail": "Access verified",
                "latency_ms": elapsed,
            })
        elif response.status_code == 429:
            europepmc_info.update({
                "status": "rate_limited",
                "detail": "Rate limited by upstream service",
                "latency_ms": elapsed,
            })
        else:
            europepmc_info.update({
                "status": "upstream_error",
                "detail": f"HTTP {response.status_code}",
                "latency_ms": elapsed,
            })
    except httpx.TimeoutException:
        europepmc_info.update({"status": "timeout", "detail": "Request timed out"})
    except httpx.HTTPError:
        europepmc_info.update({"status": "network_error", "detail": "Network/API error"})
    sources["europepmc"] = europepmc_info

    return {"checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "sources": sources}


def _owned_workspace_or_404(db: Session, workspace_id: int, user_id: int) -> Workspace:
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id, Workspace.user_id == user_id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


async def _resolve_access_payload(
    source: str,
    doi: Optional[str],
    url: Optional[str],
    pdf_url: Optional[str],
    institutional_url: Optional[str],
) -> Dict[str, Any]:
    normalized_doi = _normalize_doi(doi or "")
    url_value = str(url or "").strip()
    pdf_value = str(pdf_url or "").strip()
    institutional_value = str(institutional_url or "").strip()

    resolved_pdf = pdf_value or (url_value if _is_pdf_url(url_value) else "")
    resolution_source = "existing_link" if resolved_pdf else None

    if not resolved_pdf and normalized_doi:
        try:
            resolved_pdf = await asyncio.wait_for(
                _fetch_unpaywall_pdf(normalized_doi),
                timeout=GLOBAL_UNPAYWALL_TIMEOUT_SECONDS,
            ) or ""
            if resolved_pdf:
                resolution_source = "unpaywall"
        except asyncio.TimeoutError:
            resolved_pdf = ""

    payload: Dict[str, Any] = {
        "source": str(source or "").strip().lower() or "manual_import",
        "doi": normalized_doi or None,
        "url": url_value or None,
        "pdf_url": resolved_pdf or None,
        "institutional_url": institutional_value or None,
    }
    _annotate_access_metadata(payload)
    payload["resolution_source"] = resolution_source or (
        "institutional" if institutional_value else "heuristic"
    )
    return payload


@router.post("/import-institutional")
async def import_institutional_papers(
    payload: InstitutionalImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = _owned_workspace_or_404(db, payload.workspace_id, current_user.id)
    entries: List[InstitutionalPaperEntry] = []
    if payload.entries:
        entries.extend(payload.entries)
    if payload.raw_text:
        entries.extend(_parse_institutional_raw_text(payload.raw_text))

    if not entries:
        raise HTTPException(status_code=400, detail="No institutional entries provided.")

    imported = 0
    updated = 0
    skipped = 0
    errors: List[str] = []

    for idx, entry in enumerate(entries, start=1):
        title = str(entry.title or "").strip()
        if len(title) < 2:
            skipped += 1
            continue

        doi_norm = _normalize_doi(str(entry.doi or ""))
        existing: Optional[Paper] = None
        if doi_norm:
            existing = (
                db.query(Paper)
                .filter(Paper.workspace_id == workspace.id, Paper.doi == doi_norm)
                .first()
            )
        if not existing:
            existing = (
                db.query(Paper)
                .filter(Paper.workspace_id == workspace.id, func.lower(Paper.title) == title.lower())
                .first()
            )

        try:
            resolved = await _resolve_access_payload(
                source=payload.source_name or "institutional_portal",
                doi=doi_norm or None,
                url=entry.url,
                pdf_url=entry.pdf_url,
                institutional_url=entry.institutional_url or entry.url,
            )
        except Exception as exc:
            errors.append(f"Entry {idx}: {str(exc)[:140]}")
            skipped += 1
            continue

        if existing:
            existing.title = title[:600] or existing.title
            if entry.authors:
                existing.authors = ", ".join(entry.authors)[:2000]
            if entry.abstract:
                existing.abstract = str(entry.abstract)
            existing.url = str(entry.url or existing.url or "").strip() or existing.url
            if doi_norm:
                existing.doi = doi_norm
            existing.source = str(resolved.get("source") or existing.source or "institutional_portal")
            existing.pdf_url = str(resolved.get("pdf_url") or existing.pdf_url or "").strip() or existing.pdf_url
            existing.institutional_url = str(
                resolved.get("institutional_url") or existing.institutional_url or ""
            ).strip() or existing.institutional_url
            existing.access_type = str(resolved.get("access_type") or existing.access_type or "institutional")
            existing.full_text_available = bool(
                resolved.get("full_text_available") or existing.full_text_available
            )
            updated += 1
            continue

        paper = Paper(
            title=title[:600],
            authors=", ".join(entry.authors or [])[:2000],
            abstract=str(entry.abstract or "").strip() or "Institutional import entry.",
            url=str(entry.url or "").strip() or None,
            doi=doi_norm or None,
            source=str(resolved.get("source") or "institutional_portal"),
            pdf_url=str(resolved.get("pdf_url") or "").strip() or None,
            institutional_url=str(resolved.get("institutional_url") or "").strip() or None,
            access_type=str(resolved.get("access_type") or "institutional"),
            full_text_available=bool(resolved.get("full_text_available")),
            workspace_id=workspace.id,
        )
        db.add(paper)
        imported += 1

    db.commit()

    return {
        "workspace_id": workspace.id,
        "workspace_name": workspace.name,
        "source": str(payload.source_name or "institutional_portal").strip().lower(),
        "received": len(entries),
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:12],
    }


@router.post("/resolve-access")
async def resolve_access(
    payload: AccessResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    paper: Optional[Paper] = None
    if payload.workspace_id and payload.paper_id:
        workspace = _owned_workspace_or_404(db, payload.workspace_id, current_user.id)
        paper = (
            db.query(Paper)
            .filter(Paper.id == payload.paper_id, Paper.workspace_id == workspace.id)
            .first()
        )
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found in workspace.")

    source = payload.source or (paper.source if paper else "") or "manual_import"
    doi = payload.doi or (paper.doi if paper else "")
    url = payload.url or (paper.url if paper else "")
    pdf_url = payload.pdf_url or (paper.pdf_url if paper else "")
    institutional_url = payload.institutional_url or (paper.institutional_url if paper else "")

    resolved = await _resolve_access_payload(
        source=str(source),
        doi=doi,
        url=url,
        pdf_url=pdf_url,
        institutional_url=institutional_url,
    )

    if paper:
        if resolved.get("doi"):
            paper.doi = str(resolved.get("doi"))
        if resolved.get("url"):
            paper.url = str(resolved.get("url"))
        if resolved.get("pdf_url"):
            paper.pdf_url = str(resolved.get("pdf_url"))
        if resolved.get("institutional_url"):
            paper.institutional_url = str(resolved.get("institutional_url"))
        paper.source = str(resolved.get("source") or paper.source or "manual_import")
        paper.access_type = str(resolved.get("access_type") or "metadata_only")
        paper.full_text_available = bool(resolved.get("full_text_available"))
        db.commit()
        db.refresh(paper)

    return {
        "paper_id": paper.id if paper else None,
        "title": (paper.title if paper else payload.title) or "",
        "resolved": resolved,
    }


@router.post("/resolve-workspace-access")
async def resolve_workspace_access(
    payload: WorkspaceAccessResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = _owned_workspace_or_404(db, payload.workspace_id, current_user.id)
    rows = db.query(Paper).filter(Paper.workspace_id == workspace.id).all()
    if not rows:
        return {
            "workspace_id": workspace.id,
            "workspace_name": workspace.name,
            "processed": 0,
            "full_text_count": 0,
            "updated": 0,
            "sample": [],
        }

    unresolved = [
        row for row in rows
        if payload.refresh_all or not bool(row.full_text_available)
    ]
    max_unpaywall = max(2, min(payload.max_unpaywall_lookups, 80))
    doi_lookups_used = 0
    updated = 0
    sample: List[Dict[str, Any]] = []

    for row in unresolved:
        doi_allowed = bool(row.doi) and doi_lookups_used < max_unpaywall
        if doi_allowed:
            doi_lookups_used += 1
        resolved = await _resolve_access_payload(
            source=str(row.source or "manual_import"),
            doi=row.doi if doi_allowed else None,
            url=row.url,
            pdf_url=row.pdf_url,
            institutional_url=row.institutional_url,
        )

        previous = (
            bool(row.full_text_available),
            str(row.access_type or ""),
            str(row.pdf_url or ""),
            str(row.institutional_url or ""),
        )
        row.source = str(resolved.get("source") or row.source or "manual_import")
        row.access_type = str(resolved.get("access_type") or "metadata_only")
        row.full_text_available = bool(resolved.get("full_text_available"))
        if resolved.get("pdf_url"):
            row.pdf_url = str(resolved.get("pdf_url"))
        if resolved.get("institutional_url"):
            row.institutional_url = str(resolved.get("institutional_url"))
        after = (
            bool(row.full_text_available),
            str(row.access_type or ""),
            str(row.pdf_url or ""),
            str(row.institutional_url or ""),
        )
        if after != previous:
            updated += 1

        if len(sample) < 12:
            sample.append(
                {
                    "paper_id": row.id,
                    "title": row.title,
                    "access_type": row.access_type,
                    "full_text_available": bool(row.full_text_available),
                    "full_text_url": _paper_full_text_url_from_fields(
                        row.pdf_url,
                        row.institutional_url,
                        row.url,
                    ) or None,
                }
            )

    db.commit()

    full_text_count = (
        db.query(Paper)
        .filter(Paper.workspace_id == workspace.id, Paper.full_text_available.is_(True))
        .count()
    )

    return {
        "workspace_id": workspace.id,
        "workspace_name": workspace.name,
        "processed": len(unresolved),
        "full_text_count": int(full_text_count),
        "updated": updated,
        "doi_lookups_used": doi_lookups_used,
        "sample": sample,
    }


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

    normalized_doi = _normalize_doi(paper_data.doi or "")
    normalized_title = re.sub(r"\s+", " ", str(paper_data.title or "").strip().lower())

    existing: Optional[Paper] = None
    if normalized_doi:
        existing = (
            db.query(Paper)
            .filter(Paper.workspace_id == workspace.id, Paper.doi == normalized_doi)
            .first()
        )
    if not existing and normalized_title:
        existing = (
            db.query(Paper)
            .filter(Paper.workspace_id == workspace.id, func.lower(Paper.title) == normalized_title)
            .first()
        )

    source_name = str(paper_data.source or "manual_import").strip().lower()[:120] or "manual_import"
    pdf_url = str(paper_data.pdf_url or "").strip()
    institutional_url = str(paper_data.institutional_url or "").strip()
    full_text_url = _paper_full_text_url_from_fields(pdf_url, institutional_url, paper_data.url)
    full_text_available = (
        bool(paper_data.full_text_available)
        if paper_data.full_text_available is not None
        else bool(full_text_url)
    )

    if existing:
        existing.title = paper_data.title.strip()[:600] or existing.title
        existing.authors = ", ".join(paper_data.authors or []).strip() or existing.authors
        existing.abstract = (paper_data.abstract or "").strip() or existing.abstract
        existing.url = (paper_data.url or existing.url or "").strip() or None
        if normalized_doi:
            existing.doi = normalized_doi
        existing.bibcode = (paper_data.bibcode or existing.bibcode or "").strip() or None
        existing.source = source_name or existing.source
        existing.pdf_url = pdf_url or existing.pdf_url
        existing.institutional_url = institutional_url or existing.institutional_url
        existing.full_text_available = bool(full_text_available or existing.full_text_available)
        existing.access_type = (
            str(paper_data.access_type or "").strip().lower()
            or existing.access_type
            or ("open_access" if full_text_available else "metadata_only")
        )
        db.commit()
        db.refresh(existing)
        return {"message": "Paper updated successfully", "paper_id": existing.id, "updated": True}

    new_paper = Paper(
        title=paper_data.title.strip()[:600],
        authors=", ".join(paper_data.authors or []),
        abstract=paper_data.abstract,
        url=paper_data.url,
        doi=normalized_doi or None,
        bibcode=paper_data.bibcode,
        source=source_name,
        pdf_url=pdf_url or None,
        institutional_url=institutional_url or None,
        access_type=(str(paper_data.access_type or "").strip().lower() or ("open_access" if full_text_available else "metadata_only")),
        full_text_available=bool(full_text_available),
        workspace_id=paper_data.workspace_id,
    )
    db.add(new_paper)
    db.commit()
    db.refresh(new_paper)
    return {"message": "Paper imported successfully", "paper_id": new_paper.id, "updated": False}
