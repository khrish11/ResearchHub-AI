from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Sequence, Tuple

from google.cloud.firestore_v1.base_query import FieldFilter

from repositories import ResearchRepository
from repositories.research import Paper
from services.ai_service import run_structured_json_task
from utils.groq_client import client as groq_client


logger = logging.getLogger(__name__)

PAPER_EXPLAIN_TASK_TYPE = "explain_paper"
PAPER_EXPLAIN_COLLECTION = "paper_explanations"
PAPER_EXPLAIN_DISCLAIMER = (
    "This explanation is AI-generated from workspace data and may be incomplete. "
    "Verify conclusions against the linked paper and checker evidence."
)
DEFAULT_CACHE_HOURS = max(1, int(os.getenv("PAPER_EXPLAIN_CACHE_HOURS", "18") or 18))
DEFAULT_RAG_TOP_K = max(2, int(os.getenv("PAPER_EXPLAIN_RAG_TOP_K", "4") or 4))
DEFAULT_RAG_MAX_CONTEXT_TOKENS = max(
    400,
    int(os.getenv("PAPER_EXPLAIN_RAG_MAX_CONTEXT_TOKENS", "900") or 900),
)

_IN_MEMORY_EXPLANATIONS: Dict[str, Dict[str, Any]] = {}
_IN_MEMORY_LOCK = Lock()
_SPLIT_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _as_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return None
    return None


def _to_iso(value: Any) -> Optional[str]:
    dt = _as_datetime(value)
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _collection(repo: ResearchRepository, name: str):  # type: ignore[no-untyped-def]
    db = getattr(repo, "db", None)
    if db is None:
        return None
    try:
        return db.collection(name)
    except Exception:
        return None


def _cache_doc_id(user_id: int, paper_id: int) -> str:
    return f"pex_{int(user_id)}_{int(paper_id)}"


def _load_cached(
    *,
    repo: ResearchRepository,
    user_id: int,
    paper_id: int,
) -> Optional[Dict[str, Any]]:
    doc_id = _cache_doc_id(user_id, paper_id)
    collection = _collection(repo, PAPER_EXPLAIN_COLLECTION)
    if collection is not None:
        snapshot = collection.document(doc_id).get()
        if not snapshot.exists:
            return None
        payload = snapshot.to_dict() or {}
        return payload if isinstance(payload, dict) else None
    with _IN_MEMORY_LOCK:
        payload = _IN_MEMORY_EXPLANATIONS.get(doc_id)
        return dict(payload) if payload else None


def _persist_cached(
    *,
    repo: ResearchRepository,
    payload: Dict[str, Any],
    merge: bool = False,
) -> Dict[str, Any]:
    user_id = _coerce_int(payload.get("user_id"), 0)
    paper_id = _coerce_int(payload.get("paper_id"), 0)
    if user_id <= 0 or paper_id <= 0:
        raise ValueError("paper explanation cache payload requires user_id and paper_id")
    doc_id = _cache_doc_id(user_id, paper_id)
    body = dict(payload)
    body["explanation_id"] = doc_id
    collection = _collection(repo, PAPER_EXPLAIN_COLLECTION)
    if collection is not None:
        collection.document(doc_id).set(body, merge=bool(merge))
        snapshot = collection.document(doc_id).get()
        stored = snapshot.to_dict() or {}
        return stored if isinstance(stored, dict) else body
    with _IN_MEMORY_LOCK:
        existing = _IN_MEMORY_EXPLANATIONS.get(doc_id, {})
        if merge:
            merged = dict(existing)
            merged.update(body)
            _IN_MEMORY_EXPLANATIONS[doc_id] = merged
        else:
            _IN_MEMORY_EXPLANATIONS[doc_id] = dict(body)
        return dict(_IN_MEMORY_EXPLANATIONS[doc_id])


def _touch_cached_expiry(
    *,
    repo: ResearchRepository,
    cached_payload: Dict[str, Any],
    cache_hours: int,
) -> Dict[str, Any]:
    now = _utc_now()
    updates = {
        "paper_id": _coerce_int(cached_payload.get("paper_id"), 0),
        "user_id": _coerce_int(cached_payload.get("user_id"), 0),
        "expires_at": now + timedelta(hours=max(1, int(cache_hours))),
        "updated_at": now,
    }
    return _persist_cached(repo=repo, payload=updates, merge=True)


def _summary_sentences(text: str, limit: int = 3) -> List[str]:
    parts = [_safe_str(item) for item in _SPLIT_SENTENCE_RE.split(_safe_str(text))]
    return [part for part in parts if part][: max(1, int(limit))]


def _normalize_list(value: Any, *, max_items: int = 6, max_len: int = 260) -> List[str]:
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, tuple):
        raw_items = list(value)
    elif isinstance(value, str):
        raw_items = [segment.strip() for segment in value.split("\n") if segment.strip()]
    elif isinstance(value, dict):
        raw_items = [value]
    else:
        raw_items = []
    items: List[str] = []
    for row in raw_items:
        if isinstance(row, str):
            text = _safe_str(row)
        elif isinstance(row, dict):
            text = (
                _safe_str(row.get("text"))
                or _safe_str(row.get("point"))
                or _safe_str(row.get("item"))
                or _safe_str(row.get("claim"))
                or _safe_str(row.get("summary"))
            )
        else:
            text = _safe_str(row)
        if not text:
            continue
        clipped = text[:max_len]
        if clipped not in items:
            items.append(clipped)
        if len(items) >= max(1, int(max_items)):
            break
    return items


def _extract_checker_analysis(checker_result: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(checker_result, dict):
        return {}
    paper_analysis = checker_result.get("paper_analysis")
    return paper_analysis if isinstance(paper_analysis, dict) else {}


def _summarize_ai_likelihood(checker_result: Dict[str, Any]) -> str:
    ai_blob = (
        checker_result.get("ai_writing_likelihood")
        if isinstance(checker_result, dict)
        else None
    )
    if not isinstance(ai_blob, dict):
        return "AI-writing likelihood is unavailable. Run the AI checker to populate this signal."
    segments = ai_blob.get("segments")
    rows = segments if isinstance(segments, list) else []
    if not rows:
        detection_error = _safe_str(ai_blob.get("detection_error"))
        if detection_error:
            return f"AI-writing likelihood is unavailable ({detection_error})."
        return "No suspicious writing segments were flagged in the latest checker output."
    scores = [
        float(item.get("likelihood_score") or 0.0)
        for item in rows
        if isinstance(item, dict)
    ]
    if not scores:
        return "AI-writing likelihood signal is present but incomplete."
    max_score = max(scores)
    avg_score = sum(scores) / max(1, len(scores))
    if max_score >= 0.75:
        band = "High"
    elif max_score >= 0.45:
        band = "Medium"
    else:
        band = "Low"
    return (
        f"{band} advisory AI-writing likelihood signal "
        f"(max {max_score:.2f}, average {avg_score:.2f}); treat as non-conclusive."
    )


def _fallback_explanation(
    *,
    paper: Paper,
    checker_result: Dict[str, Any],
) -> Dict[str, Any]:
    analysis = _extract_checker_analysis(checker_result)
    snapshot = analysis.get("snapshot") if isinstance(analysis.get("snapshot"), dict) else {}
    methods = analysis.get("methods") if isinstance(analysis.get("methods"), dict) else {}
    evidence = (
        analysis.get("evidence_strength")
        if isinstance(analysis.get("evidence_strength"), dict)
        else {}
    )
    claims = analysis.get("claims") if isinstance(analysis.get("claims"), list) else []
    limitations = _normalize_list(analysis.get("limitations"), max_items=5, max_len=220)
    red_flags = _normalize_list(analysis.get("red_flags"), max_items=4, max_len=220)
    evidence_signals = _normalize_list(evidence.get("signals"), max_items=4, max_len=220)
    summary_from_snapshot = _safe_str(snapshot.get("summary"))
    abstract_summary = _summary_sentences(_safe_str(getattr(paper, "abstract", "")), limit=2)
    simple_explanation = (
        summary_from_snapshot
        or " ".join(abstract_summary)
        or "This paper's full explanation is not available yet because structured analysis data is limited."
    )
    key_points = _normalize_list(
        [
            item.get("claim")
            for item in claims
            if isinstance(item, dict) and _safe_str(item.get("claim"))
        ],
        max_items=6,
        max_len=230,
    )
    if not key_points:
        key_points = abstract_summary[:3] if abstract_summary else ["Core claims are not explicitly available in workspace metadata."]
    methodology = (
        _safe_str(methods.get("approach"))
        or "Methodology summary is limited; run the paper checker on full text for stronger method extraction."
    )
    strengths = evidence_signals or _normalize_list(
        [item.get("evidence") for item in claims if isinstance(item, dict)],
        max_items=4,
        max_len=200,
    )
    if not strengths:
        strengths = ["A clear strength could not be extracted from available context."]
    weaknesses = limitations + [item for item in red_flags if item not in limitations]
    if not weaknesses:
        weaknesses = ["Weakness details are unavailable in current workspace context."]
    evidence_score = evidence.get("score")
    evidence_summary = _safe_str(evidence.get("summary"))
    evidence_quality = evidence_summary
    if evidence_score is not None:
        try:
            evidence_quality = f"{evidence_summary or 'Evidence signal available'} (score {float(evidence_score):.2f}/1.00)."
        except Exception:
            evidence_quality = evidence_summary or "Evidence quality score is present but not parseable."
    if not evidence_quality:
        evidence_quality = "Evidence quality is uncertain because structured checker evidence is missing."
    significance = (
        _safe_str(snapshot.get("core_problem"))
        or summary_from_snapshot
        or "The paper may matter for this workspace, but significance should be confirmed against full text."
    )
    return {
        "simple_explanation": simple_explanation[:1400],
        "key_points": key_points[:6],
        "methodology": methodology[:1000],
        "strengths": strengths[:6],
        "weaknesses": weaknesses[:6],
        "evidence_quality": evidence_quality[:900],
        "ai_likelihood": _summarize_ai_likelihood(checker_result)[:500],
        "significance": significance[:900],
    }


def _normalize_explanation_payload(
    *,
    parsed_payload: Any,
    fallback_payload: Dict[str, Any],
) -> Dict[str, Any]:
    parsed = parsed_payload if isinstance(parsed_payload, dict) else {}

    def _text(key: str, fallback_key: str, max_len: int) -> str:
        value = _safe_str(parsed.get(key))
        if not value:
            value = _safe_str(fallback_payload.get(fallback_key))
        return value[:max_len]

    normalized = {
        "simple_explanation": _text("simple_explanation", "simple_explanation", 1400),
        "key_points": _normalize_list(
            parsed.get("key_points"),
            max_items=6,
            max_len=230,
        )
        or _normalize_list(fallback_payload.get("key_points"), max_items=6, max_len=230),
        "methodology": _text("methodology", "methodology", 1000),
        "strengths": _normalize_list(parsed.get("strengths"), max_items=6, max_len=210)
        or _normalize_list(fallback_payload.get("strengths"), max_items=6, max_len=210),
        "weaknesses": _normalize_list(parsed.get("weaknesses"), max_items=6, max_len=210)
        or _normalize_list(fallback_payload.get("weaknesses"), max_items=6, max_len=210),
        "evidence_quality": _text("evidence_quality", "evidence_quality", 900),
        "ai_likelihood": _text("ai_likelihood", "ai_likelihood", 500),
        "significance": _text("significance", "significance", 900),
    }
    return normalized


def _checker_row_updated_at(row: Dict[str, Any]) -> Optional[str]:
    return _to_iso(row.get("updated_at")) or _to_iso(row.get("created_at"))


def _extract_checker_context(checker_result: Dict[str, Any]) -> str:
    if not isinstance(checker_result, dict):
        return ""
    analysis = _extract_checker_analysis(checker_result)
    snapshot = analysis.get("snapshot") if isinstance(analysis.get("snapshot"), dict) else {}
    methods = analysis.get("methods") if isinstance(analysis.get("methods"), dict) else {}
    claims = analysis.get("claims") if isinstance(analysis.get("claims"), list) else []
    evidence_strength = (
        analysis.get("evidence_strength")
        if isinstance(analysis.get("evidence_strength"), dict)
        else {}
    )
    lines: List[str] = ["## Checker Context"]
    summary = _safe_str(snapshot.get("summary"))
    if summary:
        lines.append(f"- Summary: {summary[:1800]}")
    if _safe_str(snapshot.get("core_problem")):
        lines.append(f"- Core problem: {_safe_str(snapshot.get('core_problem'))[:700]}")
    approach = _safe_str(methods.get("approach"))
    if approach:
        lines.append(f"- Method approach: {approach[:1200]}")
    datasets = _normalize_list(methods.get("datasets"), max_items=6, max_len=120)
    if datasets:
        lines.append(f"- Datasets: {', '.join(datasets)}")
    metrics = _normalize_list(methods.get("metrics"), max_items=6, max_len=100)
    if metrics:
        lines.append(f"- Metrics: {', '.join(metrics)}")
    claim_rows = _normalize_list(
        [item.get("claim") for item in claims if isinstance(item, dict)],
        max_items=6,
        max_len=260,
    )
    if claim_rows:
        lines.append("- Claims:")
        lines.extend([f"  - {item}" for item in claim_rows])
    evidence_summary = _safe_str(evidence_strength.get("summary"))
    if evidence_summary:
        lines.append(f"- Evidence strength: {evidence_summary[:900]}")
    lines.append(f"- AI-writing likelihood: {_summarize_ai_likelihood(checker_result)}")
    return "\n".join(lines)[:7000]


async def _build_rag_context(
    *,
    repo: ResearchRepository,
    paper: Paper,
) -> Tuple[str, List[Dict[str, Any]]]:
    workspace_id = _coerce_int(getattr(paper, "workspace_id", 0), 0)
    if workspace_id <= 0:
        return "", []
    try:
        from services.rag_runtime import get_rag_runtime

        runtime = get_rag_runtime(db=getattr(repo, "db", None))
        retrieval_query = (
            f"Explain paper for fast onboarding: {paper.title}. "
            "Return methods, strengths, weaknesses, evidence quality, and why it matters."
        )
        rows = await runtime.retrieval_service.retrieve(
            query=retrieval_query,
            workspace_id=workspace_id,
            top_k=DEFAULT_RAG_TOP_K,
            source_types=["paper", "summary", "checker", "report"],
            min_similarity=0.3,
        )
        trimmed = runtime.retrieval_service.truncate_results_for_context(
            rows,
            max_context_tokens=DEFAULT_RAG_MAX_CONTEXT_TOKENS,
        )
        if not trimmed:
            return "", []
        lines: List[str] = ["## Workspace Context"]
        sources: List[Dict[str, Any]] = []
        for index, row in enumerate(trimmed, start=1):
            metadata = row.metadata or {}
            title = _safe_str(metadata.get("title")) or "Untitled"
            lines.extend(
                [
                    f"### Source {index}",
                    f"- source_id: {_safe_str(row.source_id)}",
                    f"- source_type: {_safe_str(row.source_type)}",
                    f"- title: {title}",
                    f"- similarity: {float(row.similarity_score):.3f}",
                    _safe_str(row.text)[:1800],
                ]
            )
            sources.append(
                {
                    "source_index": index,
                    "source_id": _safe_str(row.source_id),
                    "source_type": _safe_str(row.source_type) or "unknown",
                    "title": title,
                    "url": _safe_str(metadata.get("url")),
                    "doi": _safe_str(metadata.get("doi")),
                    "similarity_score": round(float(row.similarity_score), 4),
                }
            )
        return "\n".join(lines)[:13000], sources
    except Exception as exc:
        logger.debug(
            "paper_explain rag context skipped paper_id=%s: %s",
            getattr(paper, "id", None),
            exc,
        )
        return "", []


def _build_fingerprint(
    *,
    paper: Paper,
    checker_row: Optional[Dict[str, Any]],
    include_rag: bool,
) -> str:
    checker_result = (
        checker_row.get("result")
        if isinstance(checker_row, dict) and isinstance(checker_row.get("result"), dict)
        else {}
    )
    checker_hash_basis = json.dumps(
        checker_result,
        ensure_ascii=True,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    fingerprint_basis = {
        "paper_id": int(getattr(paper, "id", 0) or 0),
        "workspace_id": int(getattr(paper, "workspace_id", 0) or 0),
        "title": _safe_str(getattr(paper, "title", ""))[:260],
        "authors": _safe_str(getattr(paper, "authors", ""))[:500],
        "abstract": _safe_str(getattr(paper, "abstract", ""))[:2400],
        "doi": _safe_str(getattr(paper, "doi", ""))[:160],
        "url": _safe_str(getattr(paper, "url", ""))[:220],
        "source": _safe_str(getattr(paper, "source", ""))[:120],
        "checker_job_id": _safe_str((checker_row or {}).get("job_id")),
        "checker_updated_at": _checker_row_updated_at(checker_row or {}),
        "checker_result_hash": hashlib.sha256(
            checker_hash_basis.encode("utf-8")
        ).hexdigest(),
        "include_rag": bool(include_rag),
    }
    serialized = json.dumps(
        fingerprint_basis,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _explain_system_prompt() -> str:
    return (
        "You are Soyog AI's paper explainer.\n"
        "Use ONLY provided paper metadata, checker outputs, and workspace context.\n"
        "Do not hallucinate facts, methods, metrics, or claims.\n"
        "If evidence is missing, state uncertainty explicitly.\n"
        "Return strict JSON only."
    )


def _explain_user_prompt(
    *,
    paper: Paper,
    checker_context: str,
    rag_context: str,
) -> str:
    schema = (
        "{\n"
        '  "simple_explanation": "string",\n'
        '  "key_points": ["string"],\n'
        '  "methodology": "string",\n'
        '  "strengths": ["string"],\n'
        '  "weaknesses": ["string"],\n'
        '  "evidence_quality": "string",\n'
        '  "ai_likelihood": "string",\n'
        '  "significance": "string"\n'
        "}"
    )
    metadata_block = (
        "## Paper Metadata\n"
        f"- Title: {_safe_str(getattr(paper, 'title', ''))}\n"
        f"- Authors: {_safe_str(getattr(paper, 'authors', ''))}\n"
        f"- Source: {_safe_str(getattr(paper, 'source', ''))}\n"
        f"- DOI: {_safe_str(getattr(paper, 'doi', ''))}\n"
        f"- URL: {_safe_str(getattr(paper, 'url', ''))}\n"
        f"- Abstract: {_safe_str(getattr(paper, 'abstract', ''))[:3500]}\n"
    )
    instructions = (
        "Write concise, clear language for first-time readers.\n"
        "Constraints:\n"
        "- key_points, strengths, weaknesses: max 6 items each.\n"
        "- Every statement must be grounded in provided evidence.\n"
        "- If evidence is weak, mention uncertainty in evidence_quality.\n"
        "- ai_likelihood must be advisory language only.\n"
    )
    return (
        f"{metadata_block}\n"
        f"{checker_context or '## Checker Context\\n- No checker context available.'}\n\n"
        f"{rag_context or ''}\n\n"
        f"{instructions}\n"
        f"Output schema:\n{schema}"
    )[:32000]


def _find_latest_completed_checker_result(
    *,
    repo: ResearchRepository,
    paper_id: int,
    user_id: int,
) -> Optional[Dict[str, Any]]:
    db = getattr(repo, "db", None)
    if db is None:
        return None
    try:
        snapshots = db.collection("paper_check_jobs").where(
            filter=FieldFilter("paper_id", "==", int(paper_id))
        ).stream()
    except Exception:
        snapshots = db.collection("paper_check_jobs").stream()
    best_row: Optional[Dict[str, Any]] = None
    best_time: Optional[datetime] = None
    for snapshot in snapshots:
        row = snapshot.to_dict() or {}
        if _coerce_int(row.get("paper_id"), 0) != int(paper_id):
            continue
        if _coerce_int(row.get("user_id"), 0) != int(user_id):
            continue
        if _safe_str(row.get("status")).lower() != "completed":
            continue
        candidate_time = _as_datetime(row.get("updated_at")) or _as_datetime(row.get("created_at")) or _utc_now()
        if best_row is None or candidate_time > (best_time or candidate_time):
            best_row = dict(row)
            best_row["job_id"] = _safe_str(row.get("job_id") or snapshot.id)
            best_time = candidate_time
    return best_row


def _merge_sources(
    *,
    paper: Paper,
    checker_row: Optional[Dict[str, Any]],
    rag_sources: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = [
        {
            "source_id": f"paper:{int(getattr(paper, 'id', 0) or 0)}",
            "source_type": "paper",
            "title": _safe_str(getattr(paper, "title", "")) or "Paper",
            "url": _safe_str(getattr(paper, "url", "")),
            "doi": _safe_str(getattr(paper, "doi", "")),
        }
    ]
    if checker_row and isinstance(checker_row.get("result"), dict):
        sources.append(
            {
                "source_id": _safe_str(checker_row.get("job_id")) or "paper_checker_latest",
                "source_type": "checker",
                "title": f"Paper checker output for {_safe_str(getattr(paper, 'title', 'paper'))[:120]}",
                "url": _safe_str(getattr(paper, "url", "")),
                "doi": _safe_str(getattr(paper, "doi", "")),
            }
        )
    for row in rag_sources:
        if not isinstance(row, dict):
            continue
        sources.append(
            {
                "source_id": _safe_str(row.get("source_id")),
                "source_type": _safe_str(row.get("source_type")) or "unknown",
                "title": _safe_str(row.get("title")) or "Untitled",
                "url": _safe_str(row.get("url")),
                "doi": _safe_str(row.get("doi")),
                "similarity_score": float(row.get("similarity_score") or 0.0),
            }
        )
    deduped: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str, str]] = set()
    for row in sources:
        key = (
            _safe_str(row.get("source_id")),
            _safe_str(row.get("source_type")),
            _safe_str(row.get("title")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped[:12]


def _response_from_cached(
    *,
    payload: Dict[str, Any],
    status: str,
    cached: bool,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "paper_id": _coerce_int(payload.get("paper_id"), 0),
        "workspace_id": _coerce_int(payload.get("workspace_id"), 0),
        "status": status,
        "cached": bool(cached),
        "generated_at": _to_iso(payload.get("generated_at")),
        "expires_at": _to_iso(payload.get("expires_at")),
        "disclaimer": _safe_str(payload.get("disclaimer")) or PAPER_EXPLAIN_DISCLAIMER,
        "sources": payload.get("sources") if isinstance(payload.get("sources"), list) else [],
        "simple_explanation": _safe_str(payload.get("simple_explanation")),
        "key_points": _normalize_list(payload.get("key_points"), max_items=6, max_len=230),
        "methodology": _safe_str(payload.get("methodology")),
        "strengths": _normalize_list(payload.get("strengths"), max_items=6, max_len=210),
        "weaknesses": _normalize_list(payload.get("weaknesses"), max_items=6, max_len=210),
        "evidence_quality": _safe_str(payload.get("evidence_quality")),
        "ai_likelihood": _safe_str(payload.get("ai_likelihood")),
        "significance": _safe_str(payload.get("significance")),
        "error": _safe_str(error) or None,
    }


async def get_or_generate_paper_explanation(
    *,
    repo: ResearchRepository,
    paper: Paper,
    user_id: int,
    refresh: bool = False,
    include_rag: bool = False,
) -> Dict[str, Any]:
    uid = int(user_id)
    paper_id = int(getattr(paper, "id", 0) or 0)
    if uid <= 0 or paper_id <= 0:
        raise ValueError("Valid user_id and paper.id are required.")

    checker_row = _find_latest_completed_checker_result(
        repo=repo,
        paper_id=paper_id,
        user_id=uid,
    )
    checker_result = (
        checker_row.get("result")
        if isinstance(checker_row, dict) and isinstance(checker_row.get("result"), dict)
        else {}
    )
    fingerprint = _build_fingerprint(
        paper=paper,
        checker_row=checker_row,
        include_rag=bool(include_rag),
    )
    cached = _load_cached(repo=repo, user_id=uid, paper_id=paper_id)
    now = _utc_now()

    if cached and not refresh and _safe_str(cached.get("fingerprint")) == fingerprint:
        expires_at = _as_datetime(cached.get("expires_at"))
        if expires_at and expires_at > now:
            return _response_from_cached(payload=cached, status="cached", cached=True)
        touched = _touch_cached_expiry(
            repo=repo,
            cached_payload=cached,
            cache_hours=DEFAULT_CACHE_HOURS,
        )
        return _response_from_cached(payload=touched, status="reused", cached=True)

    rag_context = ""
    rag_sources: List[Dict[str, Any]] = []
    if include_rag:
        rag_context, rag_sources = await _build_rag_context(repo=repo, paper=paper)

    checker_context = _extract_checker_context(checker_result)
    fallback_payload = _fallback_explanation(
        paper=paper,
        checker_result=checker_result,
    )
    normalized_payload = dict(fallback_payload)
    generation_status = "fallback"
    task_error: Optional[str] = None

    if groq_client:
        response = run_structured_json_task(
            groq_client=groq_client,
            db=getattr(repo, "db", None),
            user_id=str(uid),
            task_type=PAPER_EXPLAIN_TASK_TYPE,
            query=_explain_user_prompt(
                paper=paper,
                checker_context=checker_context,
                rag_context=rag_context,
            ),
            system_prompt=_explain_system_prompt(),
            cacheable=True,
            timeout_seconds=max(
                20,
                int(os.getenv("AI_EXPLAIN_PAPER_TIMEOUT_SECONDS", "60") or 60),
            ),
            model_overrides={"response_format": {"type": "json_object"}},
            max_attempts=2,
        )
        if isinstance(response.get("parsed"), dict):
            normalized_payload = _normalize_explanation_payload(
                parsed_payload=response.get("parsed"),
                fallback_payload=fallback_payload,
            )
            generation_status = "generated"
        else:
            task_error = _safe_str(response.get("error")) or "Structured explain output was unavailable."
    else:
        task_error = "AI service is not configured."

    payload_to_store = {
        "paper_id": paper_id,
        "workspace_id": _coerce_int(getattr(paper, "workspace_id", 0), 0),
        "user_id": uid,
        "task_type": PAPER_EXPLAIN_TASK_TYPE,
        "fingerprint": fingerprint,
        "include_rag": bool(include_rag),
        "checker_job_id": _safe_str((checker_row or {}).get("job_id")) or None,
        "simple_explanation": normalized_payload.get("simple_explanation"),
        "key_points": normalized_payload.get("key_points") or [],
        "methodology": normalized_payload.get("methodology"),
        "strengths": normalized_payload.get("strengths") or [],
        "weaknesses": normalized_payload.get("weaknesses") or [],
        "evidence_quality": normalized_payload.get("evidence_quality"),
        "ai_likelihood": normalized_payload.get("ai_likelihood"),
        "significance": normalized_payload.get("significance"),
        "sources": _merge_sources(paper=paper, checker_row=checker_row, rag_sources=rag_sources),
        "disclaimer": PAPER_EXPLAIN_DISCLAIMER,
        "generated_at": now,
        "updated_at": now,
        "expires_at": now + timedelta(hours=DEFAULT_CACHE_HOURS),
    }
    stored = _persist_cached(repo=repo, payload=payload_to_store, merge=False)
    return _response_from_cached(
        payload=stored,
        status=generation_status,
        cached=False,
        error=task_error if generation_status == "fallback" else None,
    )
