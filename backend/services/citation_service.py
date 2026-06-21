from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import random
import os
import asyncio
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import httpx

_CITATION_CACHE_TTL_SECONDS = 15 * 60
_CITATION_CACHE_MAX_ITEMS = 512
_CITATION_CACHE: Dict[str, tuple[dict[str, Any], float]] = {}
_CITATION_CACHE_LOCK = threading.Lock()
_HTTP_TIMEOUT = httpx.Timeout(6.5, connect=3.0)
_HTTP_RETRY_ATTEMPTS = max(
    1,
    int(os.environ.get("CITATION_HTTP_RETRY_ATTEMPTS", "3") or 3),
)
_HTTP_RETRY_BASE_DELAY_SECONDS = max(
    0.05,
    float(os.environ.get("CITATION_HTTP_RETRY_BASE_DELAY_SECONDS", "0.2") or 0.2),
)
_HTTP_RETRY_MAX_DELAY_SECONDS = max(
    _HTTP_RETRY_BASE_DELAY_SECONDS,
    float(os.environ.get("CITATION_HTTP_RETRY_MAX_DELAY_SECONDS", "1.5") or 1.5),
)

_DOI_PREFIX_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/)?", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _is_retryable_http_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = int(exc.response.status_code)
        return status in {408, 409, 425, 429, 500, 502, 503, 504}
    if isinstance(exc, httpx.TransportError):
        return True
    text = str(exc or "").lower()
    return any(marker in text for marker in ("timeout", "temporar", "connection reset", "503", "504", "429"))


async def _fetch_json_with_retry(url: str, *, headers: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    last_error: Optional[Exception] = None
    for attempt in range(1, _HTTP_RETRY_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                response = await client.get(url, headers=headers or {})
                response.raise_for_status()
                payload = response.json()
                return payload if isinstance(payload, dict) else None
        except Exception as exc:
            last_error = exc
            should_retry = attempt < _HTTP_RETRY_ATTEMPTS and _is_retryable_http_error(exc)
            if not should_retry:
                break
            delay = min(
                _HTTP_RETRY_MAX_DELAY_SECONDS,
                _HTTP_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)),
            ) + random.uniform(0.0, 0.05)
            await asyncio.sleep(delay)
    if last_error:
        return None
    return None


@dataclass
class CitationMetadata:
    title: str = ""
    authors: List[str] = None  # type: ignore[assignment]
    year: Optional[str] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    pages: Optional[str] = None
    issue: Optional[str] = None
    volume: Optional[str] = None
    source: Optional[str] = None

    def __post_init__(self) -> None:
        self.authors = list(self.authors or [])


def _clean_whitespace(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _normalize_doi(value: Any) -> Optional[str]:
    candidate = _clean_whitespace(value)
    if not candidate:
        return None
    candidate = _DOI_PREFIX_RE.sub("", candidate).strip().strip(".")
    return candidate or None


def _normalize_url(value: Any) -> Optional[str]:
    candidate = _clean_whitespace(value)
    return candidate or None


def _normalize_year(value: Any) -> Optional[str]:
    candidate = _clean_whitespace(value)
    if not candidate:
        return None
    match = _YEAR_RE.search(candidate)
    return match.group(0) if match else None


def _normalize_authors(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return []
        if ";" in trimmed:
            raw_items = trimmed.split(";")
        else:
            raw_items = re.split(r"\s*,\s*(?=[A-Z][a-zA-Z'\-]+\s+[A-Z])", trimmed)
            if len(raw_items) == 1 and " and " in trimmed.lower():
                raw_items = re.split(r"\s+and\s+", trimmed, flags=re.IGNORECASE)
        return [_clean_whitespace(item) for item in raw_items if _clean_whitespace(item)]
    if isinstance(value, Sequence):
        return [_clean_whitespace(item) for item in value if _clean_whitespace(item)]
    return [_clean_whitespace(value)]


def normalize_metadata(payload: Mapping[str, Any]) -> CitationMetadata:
    year = _normalize_year(payload.get("year") or payload.get("published"))
    doi = _normalize_doi(payload.get("doi"))
    url = _normalize_url(payload.get("url") or payload.get("pdf_url"))
    return CitationMetadata(
        title=_clean_whitespace(payload.get("title")),
        authors=_normalize_authors(payload.get("authors")),
        year=year,
        venue=_clean_whitespace(payload.get("venue") or payload.get("journal") or payload.get("source")) or None,
        doi=doi,
        url=url,
        pages=_clean_whitespace(payload.get("pages")) or None,
        issue=_clean_whitespace(payload.get("issue")) or None,
        volume=_clean_whitespace(payload.get("volume")) or None,
        source=_clean_whitespace(payload.get("source")) or None,
    )


def _merge_metadata(high: CitationMetadata, low: CitationMetadata) -> CitationMetadata:
    merged = CitationMetadata(
        title=high.title or low.title,
        authors=high.authors or low.authors,
        year=high.year or low.year,
        venue=high.venue or low.venue,
        doi=high.doi or low.doi,
        url=high.url or low.url,
        pages=high.pages or low.pages,
        issue=high.issue or low.issue,
        volume=high.volume or low.volume,
        source=high.source or low.source,
    )
    return merged


async def _fetch_crossref_metadata(doi: str) -> Optional[CitationMetadata]:
    if not doi:
        return None
    url = f"https://api.crossref.org/works/{doi}"
    payload = await _fetch_json_with_retry(
        url,
        headers={"User-Agent": "Soyog-AI/1.0", "Accept": "application/json"},
    )
    if not payload:
        return None

    message = payload.get("message") or {}
    authors: List[str] = []
    for author in message.get("author") or []:
        given = _clean_whitespace(author.get("given"))
        family = _clean_whitespace(author.get("family"))
        full = " ".join(part for part in (given, family) if part)
        if full:
            authors.append(full)

    published_parts = (
        (((message.get("published-print") or {}).get("date-parts") or [[]])[0])
        or (((message.get("published-online") or {}).get("date-parts") or [[]])[0])
        or (((message.get("issued") or {}).get("date-parts") or [[]])[0])
    )
    year = str(published_parts[0]) if published_parts else None
    venue_items = message.get("container-title") or []
    return CitationMetadata(
        title=_clean_whitespace((message.get("title") or [""])[0]),
        authors=authors,
        year=_normalize_year(year),
        venue=_clean_whitespace(venue_items[0] if venue_items else "") or None,
        doi=_normalize_doi(message.get("DOI") or doi),
        url=_normalize_url(message.get("URL")),
        pages=_clean_whitespace(message.get("page")) or None,
        issue=_clean_whitespace(message.get("issue")) or None,
        volume=_clean_whitespace(message.get("volume")) or None,
        source="crossref",
    )


async def _fetch_openalex_metadata(doi: str) -> Optional[CitationMetadata]:
    if not doi:
        return None
    encoded = httpx.URL(f"https://doi.org/{doi}")
    url = f"https://api.openalex.org/works/{encoded!s}"
    payload = await _fetch_json_with_retry(
        url,
        headers={"User-Agent": "Soyog-AI/1.0", "Accept": "application/json"},
    )
    if not payload:
        return None

    authors: List[str] = []
    for item in payload.get("authorships") or []:
        author_name = _clean_whitespace(((item.get("author") or {}).get("display_name")))
        if author_name:
            authors.append(author_name)
    primary_location = payload.get("primary_location") or {}
    source = primary_location.get("source") or {}
    return CitationMetadata(
        title=_clean_whitespace(payload.get("display_name")),
        authors=authors,
        year=_normalize_year(payload.get("publication_year")),
        venue=_clean_whitespace(source.get("display_name")) or None,
        doi=_normalize_doi(payload.get("doi") or doi),
        url=_normalize_url(payload.get("id") or primary_location.get("landing_page_url")),
        pages=None,
        issue=None,
        volume=None,
        source="openalex",
    )


async def resolve_best_metadata(metadata: CitationMetadata) -> CitationMetadata:
    resolved = CitationMetadata(**asdict(metadata))
    doi = _normalize_doi(metadata.doi)
    if doi:
        crossref = await _fetch_crossref_metadata(doi)
        if crossref:
            resolved = _merge_metadata(crossref, resolved)
        openalex = await _fetch_openalex_metadata(doi)
        if openalex:
            resolved = _merge_metadata(openalex, resolved)
    return resolved


def _cache_key(metadata: CitationMetadata, style: str) -> str:
    raw = json.dumps({"style": style, **asdict(metadata)}, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _get_cache(key: str) -> Optional[dict[str, Any]]:
    with _CITATION_CACHE_LOCK:
        entry = _CITATION_CACHE.get(key)
        if not entry:
            return None
        payload, created_at = entry
        if time.time() - created_at > _CITATION_CACHE_TTL_SECONDS:
            _CITATION_CACHE.pop(key, None)
            return None
        return dict(payload)


def _set_cache(key: str, value: dict[str, Any]) -> None:
    with _CITATION_CACHE_LOCK:
        if key not in _CITATION_CACHE and len(_CITATION_CACHE) >= _CITATION_CACHE_MAX_ITEMS:
            try:
                oldest = next(iter(_CITATION_CACHE))
                _CITATION_CACHE.pop(oldest, None)
            except StopIteration:
                pass
        _CITATION_CACHE[key] = (dict(value), time.time())


def _split_name(full_name: str) -> tuple[str, List[str]]:
    trimmed = _clean_whitespace(full_name)
    if not trimmed:
        return "", []
    if "," in trimmed:
        family, given = trimmed.split(",", 1)
        given_parts = [part for part in _clean_whitespace(given).split(" ") if part]
        return _clean_whitespace(family), given_parts
    parts = [part for part in trimmed.split(" ") if part]
    if len(parts) == 1:
        return parts[0], []
    return parts[-1], parts[:-1]


def _initials(parts: Iterable[str]) -> str:
    initials = []
    for part in parts:
        token = part.strip(". ")
        if not token:
            continue
        initials.append(f"{token[0].upper()}.")
    return " ".join(initials)


def _format_author_apa(full_name: str) -> str:
    family, given = _split_name(full_name)
    if not family:
        return _clean_whitespace(full_name)
    initials = _initials(given)
    return f"{family}, {initials}".strip().rstrip(",")


def _format_author_mla(full_name: str) -> str:
    family, given = _split_name(full_name)
    if not family:
        return _clean_whitespace(full_name)
    return ", ".join(part for part in (family, " ".join(given).strip()) if part)


def _format_author_ieee(full_name: str) -> str:
    family, given = _split_name(full_name)
    if not family:
        return _clean_whitespace(full_name)
    initials = _initials(given)
    return " ".join(part for part in (initials, family) if part).strip()


def _join_authors(authors: Sequence[str], formatter, *, max_names: Optional[int] = None) -> str:
    names = [formatter(author) for author in authors if _clean_whitespace(author)]
    if max_names is not None:
        names = names[:max_names]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} & {names[1]}"
    return ", ".join(names[:-1]) + f", & {names[-1]}"


def _append_locator(metadata: CitationMetadata) -> str:
    parts = []
    if metadata.volume:
        parts.append(f"vol. {metadata.volume}")
    if metadata.issue:
        parts.append(f"no. {metadata.issue}")
    if metadata.pages:
        parts.append(f"pp. {metadata.pages}")
    return ", ".join(parts)


def _reference_link(metadata: CitationMetadata) -> str:
    if metadata.doi:
        return f"https://doi.org/{metadata.doi}"
    return metadata.url or ""


def generate_apa(metadata: CitationMetadata) -> str:
    authors = _join_authors(metadata.authors, _format_author_apa)
    segments = []
    if authors:
        segments.append(authors)
    if metadata.year:
        segments.append(f"({metadata.year}).")
    if metadata.title:
        segments.append(f"{metadata.title}.")
    if metadata.venue:
        venue = metadata.venue
        locator = _append_locator(metadata)
        if locator:
            venue = f"{venue}, {locator}"
        segments.append(f"{venue}.")
    link = _reference_link(metadata)
    if link:
        segments.append(link)
    return " ".join(segment.strip() for segment in segments if segment.strip()).strip()


def generate_mla(metadata: CitationMetadata) -> str:
    authors = metadata.authors
    author_text = ""
    if authors:
        if len(authors) == 1:
            author_text = f"{_format_author_mla(authors[0])}."
        elif len(authors) == 2:
            author_text = f"{_format_author_mla(authors[0])}, and {authors[1].strip()}."
        else:
            author_text = f"{_format_author_mla(authors[0])}, et al."
    segments = [author_text]
    if metadata.title:
        segments.append(f"\"{metadata.title}.\"")
    if metadata.venue:
        segments.append(metadata.venue)
    locator = _append_locator(metadata)
    if locator:
        segments.append(locator)
    if metadata.year:
        segments.append(metadata.year)
    link = _reference_link(metadata)
    if link:
        segments.append(link)
    return " ".join(segment.strip().rstrip(",") for segment in segments if segment.strip()).strip() + "."


def generate_ieee(metadata: CitationMetadata) -> str:
    author_text = _join_authors(metadata.authors, _format_author_ieee)
    segments = []
    if author_text:
        segments.append(author_text)
    if metadata.title:
        segments.append(f"\"{metadata.title},\"")
    if metadata.venue:
        venue = metadata.venue
        locator = _append_locator(metadata)
        if locator:
            venue = f"{venue}, {locator}"
        segments.append(venue)
    if metadata.year:
        segments.append(metadata.year)
    link = _reference_link(metadata)
    if link:
        segments.append(link)
    return ", ".join(segment.strip().rstrip(",") for segment in segments if segment.strip()).strip(". ") + "."


def generate_chicago(metadata: CitationMetadata) -> str:
    authors = metadata.authors
    author_text = ""
    if authors:
        if len(authors) == 1:
            author_text = _format_author_mla(authors[0])
        elif len(authors) == 2:
            author_text = f"{_format_author_mla(authors[0])} and {authors[1].strip()}"
        else:
            author_text = f"{_format_author_mla(authors[0])} et al"
    segments = []
    if author_text:
        segments.append(f"{author_text}.")
    if metadata.title:
        segments.append(f"\"{metadata.title}.\"")
    if metadata.venue:
        venue = metadata.venue
        locator = _append_locator(metadata)
        if locator:
            venue = f"{venue}, {locator}"
        if metadata.year:
            segments.append(f"{venue} ({metadata.year}).")
        else:
            segments.append(f"{venue}.")
    elif metadata.year:
        segments.append(f"({metadata.year}).")
    link = _reference_link(metadata)
    if link:
        segments.append(link)
    return " ".join(segment.strip() for segment in segments if segment.strip()).strip()


def generate_bibtex(metadata: CitationMetadata) -> str:
    entry_type = "article" if metadata.venue else "misc"
    first_author = metadata.authors[0] if metadata.authors else "paper"
    family, _ = _split_name(first_author)
    title_token = re.sub(r"[^a-zA-Z0-9]+", "", (metadata.title or "paper").split(" ")[0]).lower() or "paper"
    key = f"{(family or 'paper').lower()}{metadata.year or 'nd'}{title_token}"
    fields = [
        f"  title = {{{metadata.title}}}," if metadata.title else "",
        f"  author = {{{' and '.join(metadata.authors)}}}," if metadata.authors else "",
        f"  year = {{{metadata.year}}}," if metadata.year else "",
        f"  journal = {{{metadata.venue}}}," if metadata.venue else "",
        f"  volume = {{{metadata.volume}}}," if metadata.volume else "",
        f"  number = {{{metadata.issue}}}," if metadata.issue else "",
        f"  pages = {{{metadata.pages}}}," if metadata.pages else "",
        f"  doi = {{{metadata.doi}}}," if metadata.doi else "",
        f"  url = {{{_reference_link(metadata)}}}," if _reference_link(metadata) else "",
    ]
    filtered = "\n".join(field for field in fields if field)
    return f"@{entry_type}{{{key},\n{filtered}\n}}"


def compute_completeness(metadata: CitationMetadata) -> tuple[int, List[str], List[str]]:
    score = 0
    missing: List[str] = []
    warnings: List[str] = []

    if metadata.title:
        score += 20
    else:
        missing.append("title")
    if metadata.authors:
        score += 20
    else:
        missing.append("authors")
    if metadata.year:
        score += 15
    else:
        missing.append("year")
    if metadata.venue:
        score += 15
    else:
        missing.append("venue")
    if metadata.doi:
        score += 10
    else:
        missing.append("doi")
    if metadata.url:
        score += 10
    else:
        missing.append("url")
    if metadata.pages or metadata.issue or metadata.volume:
        score += 10
    else:
        missing.append("pages_or_issue")

    if not metadata.title or not metadata.authors:
        warnings.append("Citation is missing core bibliographic fields.")
    if not metadata.year or not metadata.venue:
        warnings.append("Citation may be incomplete for formal academic submission.")
    if metadata.url and not metadata.doi:
        warnings.append("Using URL fallback because DOI is unavailable.")

    return max(0, min(100, score)), missing, warnings


def _format_by_style(metadata: CitationMetadata, style: str) -> str:
    lowered = str(style or "apa").strip().lower()
    if lowered == "mla":
        return generate_mla(metadata)
    if lowered == "ieee":
        return generate_ieee(metadata)
    if lowered == "chicago":
        return generate_chicago(metadata)
    if lowered == "bibtex":
        return generate_bibtex(metadata)
    return generate_apa(metadata)


async def build_citation_response(payload: Mapping[str, Any], style: str = "apa") -> dict[str, Any]:
    metadata = normalize_metadata(payload)
    cache_key = _cache_key(metadata, style)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    resolved = await resolve_best_metadata(metadata)
    citation = _format_by_style(resolved, style)
    completeness_score, missing_fields, warnings = compute_completeness(resolved)
    response = {
        "citation": citation,
        "style": str(style or "apa").strip().lower() or "apa",
        "completeness_score": completeness_score,
        "missing_fields": missing_fields,
        "warnings": warnings,
        "metadata": {
            "title": resolved.title,
            "authors": resolved.authors,
            "year": resolved.year,
            "venue": resolved.venue,
            "doi": resolved.doi,
            "url": resolved.url,
            "pages": resolved.pages,
            "issue": resolved.issue,
            "volume": resolved.volume,
            "source": resolved.source,
        },
    }
    _set_cache(cache_key, response)
    return response
