from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import statistics
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence
from uuid import uuid4

from repositories import ResearchRepository
from repositories.research import Paper, PaperCheckJob
from services.ai_service import run_structured_json_task
from utils.paper_check_pubsub import PaperCheckPubSubError, publish_paper_check_job
from services.pdf_text_service import clean_extracted_text, extract_text_from_pdf_bytes
from utils.firebase_storage import download_bytes
from utils.groq_client import client as groq_client

logger = logging.getLogger(__name__)

ADVISORY_DISCLAIMER = (
    "This analysis is advisory and may be incorrect. "
    "It should not be used as proof of AI authorship."
)
SERVICE_VERSION = "paper-check-v1"
JOB_TIMEOUT_SECONDS = 120
MAX_ACTIVE_JOBS_PER_USER = max(0, int(os.getenv("PAPER_CHECK_MAX_ACTIVE_JOBS_PER_USER", "0") or 0))
HIGH_LATENCY_WARNING_MS = max(5000, int(os.getenv("PAPER_CHECK_HIGH_LATENCY_WARNING_MS", "45000") or 45000))
QUEUE_PARTITION_COUNT = max(1, int(os.getenv("PAPER_CHECK_QUEUE_PARTITIONS", "8") or 8))
QUEUE_DEPTH_WARN_THRESHOLD = max(0, int(os.getenv("PAPER_CHECK_QUEUE_DEPTH_WARN_THRESHOLD", "0") or 0))
QUEUE_DEPTH_WARN_INTERVAL_SECONDS = max(5.0, float(os.getenv("PAPER_CHECK_QUEUE_DEPTH_WARN_INTERVAL_SECONDS", "30") or 30))
_TEXT_CACHE_TTL_SECONDS = 20 * 60
_TEXT_CACHE_MAX_ITEMS = 128
_TEXT_CACHE: Dict[str, tuple[str, float]] = {}
_TEXT_CACHE_LOCK = threading.Lock()
_QUEUE_DEPTH_STATE: Dict[str, float] = {"last_checked_at": 0.0, "last_pending_count": 0.0}
_QUEUE_DEPTH_LOCK = threading.Lock()

_TRANSITION_PHRASES = (
    "furthermore",
    "moreover",
    "in addition",
    "in conclusion",
    "overall",
    "therefore",
    "however",
    "thus",
    "notably",
    "it is important to note",
    "this paper presents",
    "this study presents",
)
_GENERIC_PHRASES = (
    "state of the art",
    "significant improvement",
    "robust results",
    "comprehensive evaluation",
    "promising results",
    "future work",
)
_SECTION_HEADING_RE = re.compile(
    r"^(abstract|introduction|background|related work|method|methods|methodology|results|discussion|conclusion|limitations|references)\s*$",
    re.IGNORECASE,
)
_CITATION_PATTERN_RE = re.compile(
    r"\[[0-9,\-\s]+\]|\([A-Z][A-Za-z\-]+(?:\s+et al\.)?,?\s*(?:19|20)\d{2}\)|\bdoi\b",
    re.IGNORECASE,
)
_JOB_PRIORITY_VALUES = {"low", "normal", "high"}
_JOB_PRIORITY_ORDER = {"high": 3, "normal": 2, "low": 1}
_JOB_TYPE_VALUES = {"fast", "heavy"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


_PUBLISH_RATE_LIMIT_TOKENS = max(1.0, float(os.getenv("PAPER_CHECK_PUBLISH_RATE_LIMIT", "50.0") or 50.0))
_RATE_LIMIT_STATE = {"tokens": _PUBLISH_RATE_LIMIT_TOKENS, "last_refill": time.time()}
_RATE_LIMIT_LOCK = threading.Lock()

def _check_publish_rate_limit() -> bool:
    if _PUBLISH_RATE_LIMIT_TOKENS >= 10000:
        return True
    with _RATE_LIMIT_LOCK:
        now = time.time()
        elapsed = now - _RATE_LIMIT_STATE["last_refill"]
        _RATE_LIMIT_STATE["tokens"] = min(
            _PUBLISH_RATE_LIMIT_TOKENS,
            _RATE_LIMIT_STATE["tokens"] + elapsed * _PUBLISH_RATE_LIMIT_TOKENS
        )
        _RATE_LIMIT_STATE["last_refill"] = now
        
        if _RATE_LIMIT_STATE["tokens"] >= 1.0:
            _RATE_LIMIT_STATE["tokens"] -= 1.0
            return True
        return False


def _log_job_event(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, default=str))


def _publish_job_trigger(
    job_id: str,
    *,
    reason: str,
    priority: str = "normal",
    job_type: str = "fast",
    queue_partition: Optional[int] = None,
) -> None:
    if not _check_publish_rate_limit():
        logger.warning(
            json.dumps({"event": "paper_check_publish_rate_limited", "job_id": job_id})
        )
        return

    try:
        message_id = publish_paper_check_job(
            job_id,
            reason=reason,
            priority=priority,
            job_type=job_type,
            queue_partition=queue_partition,
        )
        _log_job_event(
            "paper_check_job_dispatched",
            job_id=job_id,
            reason=reason,
            message_id=message_id,
            priority=priority,
            job_type=job_type,
            queue_partition=queue_partition,
        )
    except Exception as exc:
        level = logging.WARNING if isinstance(exc, PaperCheckPubSubError) else logging.ERROR
        logger.log(
            level,
            json.dumps(
                {
                    "event": "paper_check_job_dispatch_failed",
                    "job_id": job_id,
                    "reason": reason,
                    "priority": priority,
                    "job_type": job_type,
                    "queue_partition": queue_partition,
                    "error": str(exc),
                },
                default=str,
            ),
        )


def _normalize_job_priority(raw_priority: Optional[str]) -> str:
    value = str(raw_priority or "normal").strip().lower()
    if value not in _JOB_PRIORITY_VALUES:
        return "normal"
    return value


def _normalize_job_type(raw_job_type: Optional[str]) -> str:
    value = str(raw_job_type or "fast").strip().lower()
    if value not in _JOB_TYPE_VALUES:
        return "fast"
    return value


def _compute_queue_partition(job_id: str) -> int:
    if QUEUE_PARTITION_COUNT <= 1:
        return 0
    digest = hashlib.sha256(str(job_id).encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % QUEUE_PARTITION_COUNT


def _warn_on_queue_depth(
    *,
    repo: ResearchRepository,
) -> None:
    if QUEUE_DEPTH_WARN_THRESHOLD <= 0:
        return
    now = time.time()
    with _QUEUE_DEPTH_LOCK:
        last_checked = float(_QUEUE_DEPTH_STATE.get("last_checked_at") or 0.0)
        if now - last_checked < QUEUE_DEPTH_WARN_INTERVAL_SECONDS:
            return
        _QUEUE_DEPTH_STATE["last_checked_at"] = now
        previous_pending = int(_QUEUE_DEPTH_STATE.get("last_pending_count") or 0)
    try:
        pending_jobs = int(repo.count_jobs_by_status(statuses=("pending",)))
    except Exception as exc:
        logger.warning(
            json.dumps(
                {
                    "event": "paper_check_queue_depth_check_failed",
                    "error": str(exc),
                },
                default=str,
            )
        )
        return
    with _QUEUE_DEPTH_LOCK:
        _QUEUE_DEPTH_STATE["last_pending_count"] = pending_jobs
    if pending_jobs >= QUEUE_DEPTH_WARN_THRESHOLD:
        logger.warning(
            json.dumps(
                {
                    "event": "paper_check_queue_depth_warning",
                    "pending_jobs": pending_jobs,
                    "warn_threshold": QUEUE_DEPTH_WARN_THRESHOLD,
                },
                default=str,
            )
        )
    if previous_pending > 0 and pending_jobs >= int(previous_pending * 1.5):
        logger.warning(
            json.dumps(
                {
                    "event": "paper_check_queue_backlog_growth",
                    "pending_jobs": pending_jobs,
                    "previous_pending_jobs": previous_pending,
                },
                default=str,
            )
        )


def _cache_get(key: str) -> Optional[str]:
    with _TEXT_CACHE_LOCK:
        entry = _TEXT_CACHE.get(key)
        if not entry:
            return None
        text, created_at = entry
        if time.time() - created_at > _TEXT_CACHE_TTL_SECONDS:
            _TEXT_CACHE.pop(key, None)
            return None
        return text


def _cache_set(key: str, text: str) -> None:
    with _TEXT_CACHE_LOCK:
        if key not in _TEXT_CACHE and len(_TEXT_CACHE) >= _TEXT_CACHE_MAX_ITEMS:
            try:
                oldest = next(iter(_TEXT_CACHE))
                _TEXT_CACHE.pop(oldest, None)
            except StopIteration:
                pass
        _TEXT_CACHE[key] = (text, time.time())


def create_job(
    *,
    repo: ResearchRepository,
    user_id: int,
    paper_id: Optional[int],
    fingerprint: Optional[str],
    priority: str,
    job_type: str,
    raw_text: Optional[str],
    workspace_id: Optional[int],
) -> PaperCheckJob:
    job_id = uuid4().hex
    queue_partition = _compute_queue_partition(job_id)
    return repo.create_paper_check_job(
        job_id=job_id,
        user_id=int(user_id),
        paper_id=int(paper_id) if paper_id is not None else None,
        fingerprint=str(fingerprint or "") or None,
        queue_partition=queue_partition,
        priority=_normalize_job_priority(priority),
        job_type=_normalize_job_type(job_type),
        input_data={
            "text": str(raw_text or "") or None,
            "workspace_id": str(workspace_id) if workspace_id is not None else None,
        },
        status="pending",
        result=None,
        error=None,
        retryable=False,
    )


def build_job_fingerprint(
    *,
    raw_text: Optional[str],
    paper_id: Optional[int],
    workspace_id: Optional[int],
) -> str:
    basis = json.dumps(
        {
            "paper_id": int(paper_id) if paper_id is not None else None,
            "workspace_id": int(workspace_id) if workspace_id is not None else None,
            "text": str(raw_text or "").strip(),
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def get_job(
    *,
    repo: ResearchRepository,
    job_id: str,
    user_id: int,
) -> Optional[PaperCheckJob]:
    row = repo.get_paper_check_job(job_id)
    if not row or int(row.user_id) != int(user_id):
        return None
    return row


def _serialize_job(job: PaperCheckJob) -> Dict[str, Any]:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "result": job.result if job.status == "completed" else None,
        "error": (
            {
                "message": job.error,
                "retryable": bool(job.retryable),
            }
            if job.error
            else None
        ),
        "created_at": (job.created_at or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z"),
        "updated_at": (job.updated_at or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z"),
        "fingerprint": job.fingerprint,
        "latency_ms": job.latency_ms,
    }


def get_job_status(
    *,
    repo: ResearchRepository,
    job_id: str,
    user_id: int,
) -> Optional[Dict[str, Any]]:
    row = get_job(repo=repo, job_id=job_id, user_id=user_id)
    if not row:
        return None
    return _serialize_job(row)


def _normalize_text(text: str) -> str:
    cleaned = clean_extracted_text(text)
    cleaned = re.sub(r"\n[ \t]*\n", "\n\n", cleaned)
    return cleaned.strip()


def _is_noise_line(line: str) -> bool:
    trimmed = line.strip()
    if not trimmed:
        return True
    if len(trimmed) <= 3 and trimmed.isdigit():
        return True
    if re.fullmatch(r"page\s+\d+", trimmed, flags=re.IGNORECASE):
        return True
    if re.fullmatch(r"\d+\s*/\s*\d+", trimmed):
        return True
    return False


def _clean_paper_text(text: str) -> str:
    lines = []
    for line in _normalize_text(text).split("\n"):
        if _is_noise_line(line):
            continue
        lines.append(line.strip())
    return "\n".join(lines).strip()


def _segment_text(text: str) -> List[Dict[str, Any]]:
    normalized = _clean_paper_text(text)
    if not normalized:
        return []

    raw_blocks = [block.strip() for block in re.split(r"\n{2,}", normalized) if block.strip()]
    if len(raw_blocks) <= 1:
        parts: List[str] = []
        buffer = []
        current_len = 0
        for line in normalized.split("\n"):
            line = line.strip()
            if not line:
                continue
            buffer.append(line)
            current_len += len(line)
            if current_len >= 900:
                parts.append(" ".join(buffer))
                buffer = []
                current_len = 0
        if buffer:
            parts.append(" ".join(buffer))
        raw_blocks = parts

    cursor = 0
    segments: List[Dict[str, Any]] = []
    for idx, block in enumerate(raw_blocks):
        start = normalized.find(block, cursor)
        if start < 0:
            start = cursor
        end = start + len(block)
        cursor = end
        segments.append(
            {
                "segment_id": f"seg_{idx+1}",
                "text": block,
                "start_offset": start,
                "end_offset": end,
                "section_heading": bool(_SECTION_HEADING_RE.match(block)),
            }
        )
    return segments


def _split_sentences(text: str) -> List[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9']+", text.lower())


def _repetition_score(tokens: Sequence[str]) -> float:
    if not tokens:
        return 0.0
    seen: Dict[str, int] = {}
    repeated = 0
    for token in tokens:
        seen[token] = seen.get(token, 0) + 1
        if seen[token] > 1:
            repeated += 1
    return min(1.0, repeated / max(1, len(tokens)))


def _transition_density(text: str, sentence_count: int) -> float:
    lowered = text.lower()
    hits = sum(lowered.count(phrase) for phrase in _TRANSITION_PHRASES)
    return hits / max(1, sentence_count)


def _generic_phrase_density(text: str) -> float:
    lowered = text.lower()
    hits = sum(lowered.count(phrase) for phrase in _GENERIC_PHRASES)
    return hits / max(1, len(_split_sentences(text)))


def _citation_density(text: str, sentence_count: int) -> float:
    hits = len(_CITATION_PATTERN_RE.findall(text))
    return hits / max(1, sentence_count)


def _sentence_metrics(sentences: Sequence[str]) -> tuple[float, float]:
    lengths = [max(1, len(_tokenize(sentence))) for sentence in sentences]
    if not lengths:
        return 0.0, 0.0
    avg = sum(lengths) / len(lengths)
    variance = statistics.pvariance(lengths) if len(lengths) > 1 else 0.0
    return avg, variance


def _suspicion_components(
    repetition_score: float,
    avg_sentence_length: float,
    variance: float,
    transition_density: float,
    citation_density: float,
    generic_density: float,
    section_heading: bool,
) -> float:
    if section_heading:
        return 0.0
    repetition_component = min(1.0, repetition_score * 2.8)
    sentence_uniformity = 1.0 - min(1.0, variance / 55.0)
    sentence_target = max(0.0, 1.0 - abs(avg_sentence_length - 18.0) / 18.0)
    transition_component = min(1.0, transition_density * 3.4)
    citation_scarcity = max(0.0, 1.0 - min(1.0, citation_density * 2.2))
    generic_component = min(1.0, generic_density * 2.4)
    return round(
        (
            repetition_component * 0.26
            + sentence_uniformity * 0.16
            + sentence_target * 0.12
            + transition_component * 0.16
            + citation_scarcity * 0.16
            + generic_component * 0.14
        ),
        4,
    )


def _heuristic_reasons(
    repetition_score: float,
    variance: float,
    transition_density: float,
    citation_density: float,
    generic_density: float,
) -> List[str]:
    reasons: List[str] = []
    if repetition_score >= 0.22:
        reasons.append("repetitive phrasing")
    if variance <= 18:
        reasons.append("uniform sentence structure")
    if transition_density >= 0.35:
        reasons.append("dense transition language")
    if citation_density <= 0.10:
        reasons.append("low citation grounding")
    if generic_density >= 0.18:
        reasons.append("generic academic phrasing")
    return reasons


def compute_segment_heuristics(text: str) -> List[Dict[str, Any]]:
    segments = _segment_text(text)
    enriched: List[Dict[str, Any]] = []
    for segment in segments:
        sentences = _split_sentences(segment["text"])
        tokens = _tokenize(segment["text"])
        repetition_score = _repetition_score(tokens)
        avg_sentence_length, variance = _sentence_metrics(sentences)
        transition_density = _transition_density(segment["text"], len(sentences))
        citation_density = _citation_density(segment["text"], len(sentences))
        generic_density = _generic_phrase_density(segment["text"])
        suspicion_score = _suspicion_components(
            repetition_score,
            avg_sentence_length,
            variance,
            transition_density,
            citation_density,
            generic_density,
            bool(segment.get("section_heading")),
        )
        reasons = _heuristic_reasons(
            repetition_score,
            variance,
            transition_density,
            citation_density,
            generic_density,
        )
        enriched.append(
            {
                **segment,
                "repetition_score": round(repetition_score, 4),
                "avg_sentence_length": round(avg_sentence_length, 2),
                "variance": round(variance, 2),
                "transition_density": round(transition_density, 4),
                "citation_density": round(citation_density, 4),
                "generic_phrase_density": round(generic_density, 4),
                "heuristic_score": suspicion_score,
                "heuristic_reasons": reasons,
                "suspicious": suspicion_score >= 0.58 and len(segment["text"]) >= 120,
            }
        )
    return enriched


def _suspicious_segments(segments: Sequence[Mapping[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
    suspicious = [dict(segment) for segment in segments if bool(segment.get("suspicious"))]
    suspicious.sort(key=lambda item: float(item.get("heuristic_score") or 0.0), reverse=True)
    if suspicious:
        return suspicious[:limit]
    fallbacks = sorted((dict(segment) for segment in segments), key=lambda item: float(item.get("heuristic_score") or 0.0), reverse=True)
    return [item for item in fallbacks[: min(limit, 3)] if float(item.get("heuristic_score") or 0.0) >= 0.45]


def _summary_metrics(segments: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not segments:
        return {
            "segment_count": 0,
            "avg_repetition_score": 0.0,
            "avg_citation_density": 0.0,
            "avg_transition_density": 0.0,
        }
    count = len(segments)
    return {
        "segment_count": count,
        "avg_repetition_score": round(sum(float(item.get("repetition_score") or 0.0) for item in segments) / count, 4),
        "avg_citation_density": round(sum(float(item.get("citation_density") or 0.0) for item in segments) / count, 4),
        "avg_transition_density": round(sum(float(item.get("transition_density") or 0.0) for item in segments) / count, 4),
    }


def _extract_text_for_paper(repo: ResearchRepository, paper: Paper, user_id: int) -> tuple[str, Dict[str, Any]]:
    file_row = repo.get_workspace_file_for_paper(paper.id, paper.workspace_id, user_id)
    if file_row and file_row.storage_path:
        cache_key = f"paper:{paper.id}:file:{file_row.storage_path}"
        cached = _cache_get(cache_key)
        if cached:
            return cached, {"source": "cache", "storage_path": file_row.storage_path, "cached": True}
        downloaded = download_bytes(storage_path=file_row.storage_path)
        extracted = _normalize_text(extract_text_from_pdf_bytes(downloaded.data))
        _cache_set(cache_key, extracted)
        return extracted, {"source": "uploaded_pdf", "storage_path": file_row.storage_path, "cached": False}

    fallback_text = "\n\n".join(
        part for part in (
            paper.title.strip() if paper.title else "",
            paper.authors.strip() if paper.authors else "",
            paper.abstract.strip() if paper.abstract else "",
        )
        if part
    ).strip()
    return fallback_text, {"source": "paper_record", "cached": False}


def _paper_check_system_prompt() -> str:
    return (
        "You are an expert scientific paper reviewer. "
        "Return ONLY valid JSON. Do not use markdown fences. "
        "Assess the paper strictly from the provided text. "
        "Schema: "
        "{"
        "\"snapshot\":{\"title\":\"\",\"paper_type\":\"\",\"core_problem\":\"\",\"summary\":\"\"},"
        "\"claims\":[{\"claim\":\"\",\"support_level\":\"high|medium|low\",\"evidence\":\"\"}],"
        "\"methods\":{\"approach\":\"\",\"datasets\":[\"\"],\"metrics\":[\"\"],\"notes\":[\"\"]},"
        "\"evidence_strength\":{\"score\":0,\"summary\":\"\",\"signals\":[\"\"]},"
        "\"reproducibility\":{\"score\":0,\"summary\":\"\",\"checklist\":[\"\"]},"
        "\"citation_quality\":{\"score\":0,\"summary\":\"\",\"issues\":[\"\"]},"
        "\"limitations\":[\"\"],"
        "\"red_flags\":[\"\"],"
        "\"confidence_notes\":[\"\"]"
        "} "
        "Use integers 0-100 for scores. If evidence is missing, say so explicitly."
    )


def _ai_writing_system_prompt() -> str:
    return (
        "You are reviewing suspicious research-paper passages for possible AI-assisted writing. "
        "Return ONLY valid JSON. Do not use markdown fences. "
        "You must be conservative. This is not proof of AI authorship. "
        "Schema: ["
        "{"
        "\"segment_id\":\"\","
        "\"likelihood_score\":0.0,"
        "\"likelihood_band\":\"low|medium|high\","
        "\"reasons\":[\"\"],"
        "\"explanation\":\"\""
        "}"
        "]"
    )


def _paper_prompt(text: str, paper: Optional[Paper], heuristics: Sequence[Mapping[str, Any]]) -> str:
    excerpt = text[:26000]
    metadata = {
        "title": paper.title if paper else None,
        "authors": paper.authors if paper else None,
        "doi": getattr(paper, "doi", None) if paper else None,
        "source": getattr(paper, "source", None) if paper else None,
        "heuristics_summary": _summary_metrics(heuristics),
    }
    return (
        "Analyze the following research paper text and produce the JSON report.\n\n"
        f"Metadata:\n{json.dumps(metadata, ensure_ascii=True)}\n\n"
        "Paper text:\n"
        f"{excerpt}"
    )


def _detection_prompt(suspicious_segments: Sequence[Mapping[str, Any]]) -> str:
    payload = [
        {
            "segment_id": item.get("segment_id"),
            "text": item.get("text"),
            "heuristic_score": item.get("heuristic_score"),
            "heuristic_reasons": item.get("heuristic_reasons"),
            "citation_density": item.get("citation_density"),
            "transition_density": item.get("transition_density"),
        }
        for item in suspicious_segments
    ]
    return (
        "Review only these suspicious passages and classify likelihood of AI-assisted writing. "
        "Be conservative and keep the output as JSON only.\n\n"
        f"{json.dumps(payload, ensure_ascii=True)}"
    )


def _fallback_analysis(text: str, paper: Optional[Paper], heuristics: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    suspicious = _suspicious_segments(heuristics)
    return {
        "snapshot": {
            "title": paper.title if paper else "Uploaded paper",
            "paper_type": "research_paper",
            "core_problem": "Unable to derive a higher-confidence problem statement without the model response.",
            "summary": "Heuristic fallback generated because structured AI analysis was unavailable.",
        },
        "claims": [
            {
                "claim": "Full paper analysis was unavailable, so only heuristic signals were computed.",
                "support_level": "low",
                "evidence": f"{len(suspicious)} suspicious segment(s) identified heuristically.",
            }
        ],
        "methods": {
            "approach": "Not fully available from fallback mode.",
            "datasets": [],
            "metrics": [],
            "notes": ["Run the checker again when the AI provider is available."],
        },
        "evidence_strength": {
            "score": 35,
            "summary": "Fallback mode cannot reliably assess evidence strength.",
            "signals": ["heuristic_only"],
        },
        "reproducibility": {
            "score": 40,
            "summary": "Reproducibility assessment requires a full structured AI pass.",
            "checklist": ["Confirm datasets", "Confirm metrics", "Confirm experimental setup"],
        },
        "citation_quality": {
            "score": 45,
            "summary": "Citation quality was estimated from citation density and available metadata only.",
            "issues": ["No full structured citation review available."],
        },
        "limitations": [
            "Structured model output was unavailable.",
            "This fallback relies on heuristics rather than full semantic review.",
        ],
        "red_flags": [
            "Use caution: fallback mode may under-report substantive paper issues.",
        ],
        "confidence_notes": [
            "Fallback heuristic mode only.",
        ],
    }


def _normalize_analysis_payload(payload: Any, paper: Optional[Paper], heuristics: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return _fallback_analysis("", paper, heuristics)
    normalized = _fallback_analysis("", paper, heuristics)
    for key in normalized.keys():
        if key in payload:
            normalized[key] = payload[key]
    return normalized


def _merge_detection_results(
    suspicious_segments: Sequence[Mapping[str, Any]],
    payload: Any,
) -> List[Dict[str, Any]]:
    parsed_by_id: Dict[str, Mapping[str, Any]] = {}
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, Mapping) and item.get("segment_id"):
                parsed_by_id[str(item.get("segment_id"))] = item

    merged: List[Dict[str, Any]] = []
    for segment in suspicious_segments:
        parsed = parsed_by_id.get(str(segment.get("segment_id"))) or {}
        likelihood_score = float(parsed.get("likelihood_score") or segment.get("heuristic_score") or 0.0)
        if likelihood_score >= 0.75:
            likelihood_band = "high"
        elif likelihood_score >= 0.45:
            likelihood_band = "medium"
        else:
            likelihood_band = "low"
        merged.append(
            {
                "segment_id": segment.get("segment_id"),
                "start_offset": segment.get("start_offset"),
                "end_offset": segment.get("end_offset"),
                "text_excerpt": str(segment.get("text") or "")[:900],
                "likelihood_score": round(max(0.0, min(1.0, likelihood_score)), 4),
                "likelihood_band": str(parsed.get("likelihood_band") or likelihood_band),
                "reasons": list(parsed.get("reasons") or segment.get("heuristic_reasons") or []),
                "explanation": str(parsed.get("explanation") or "Flag derived from heuristic review and model-assisted classification."),
                "heuristic_score": segment.get("heuristic_score"),
            }
        )
    return merged


async def run_paper_check(
    *,
    repo: ResearchRepository,
    user_id: int,
    paper_id: Optional[int] = None,
    raw_text: Optional[str] = None,
    workspace_id: Optional[int] = None,
) -> Dict[str, Any]:
    paper: Optional[Paper] = None
    source_meta: Dict[str, Any] = {}
    if paper_id is not None:
        paper = repo.find_paper_for_user(int(paper_id), int(user_id))
        if not paper:
            raise ValueError("Paper not found.")
        if workspace_id is not None and int(paper.workspace_id) != int(workspace_id):
            raise ValueError("Paper does not belong to the specified workspace.")
        text, source_meta = _extract_text_for_paper(repo, paper, int(user_id))
    else:
        text = _normalize_text(raw_text or "")

    if not text:
        raise ValueError("No paper text is available for analysis.")

    trimmed_text = text[:120000]
    heuristics = compute_segment_heuristics(trimmed_text)
    suspicious_segments = _suspicious_segments(heuristics)
    if not groq_client:
        fallback = _fallback_analysis(trimmed_text, paper, heuristics)
        return {
            "paper_analysis": fallback,
            "ai_writing_likelihood": {
                "segments": _merge_detection_results(suspicious_segments, []),
                "disclaimer": ADVISORY_DISCLAIMER,
                "detection_error": "AI service is not configured.",
            },
            "metadata": {
                "processed_at": _utc_now_iso(),
                "model_used": None,
                "version": SERVICE_VERSION,
                "source": source_meta.get("source") or ("paper_record" if paper_id is not None else "raw_text"),
                "segment_count": len(heuristics),
                "suspicious_segment_count": len(suspicious_segments),
                "cache_hit": False,
                "cache_layer": None,
            },
        }

    analysis_result = run_structured_json_task(
        groq_client=groq_client,
        db=repo.db,
        user_id=str(user_id),
        task_type="paper_check",
        query=_paper_prompt(trimmed_text, paper, heuristics),
        system_prompt=_paper_check_system_prompt(),
        cacheable=True,
    )
    paper_analysis = _normalize_analysis_payload(analysis_result.get("parsed"), paper, heuristics)
    model_used = str(analysis_result.get("model") or "")
    ai_detection_payload: Any = []
    detection_error: Optional[str] = None

    if suspicious_segments:
        detection_result = run_structured_json_task(
            groq_client=groq_client,
            db=repo.db,
            user_id=str(user_id),
            task_type="ai_writing_detection",
            query=_detection_prompt(suspicious_segments),
            system_prompt=_ai_writing_system_prompt(),
            cacheable=True,
        )
        ai_detection_payload = detection_result.get("parsed") or []
        if not model_used:
            model_used = str(detection_result.get("model") or "")
        if detection_result.get("error") and not detection_result.get("parsed"):
            detection_error = str(detection_result.get("error"))

    if analysis_result.get("error") and analysis_result.get("parsed") is None:
        paper_analysis = _fallback_analysis(trimmed_text, paper, heuristics)

    segments = _merge_detection_results(suspicious_segments, ai_detection_payload)
    return {
        "paper_analysis": paper_analysis,
        "ai_writing_likelihood": {
            "segments": segments,
            "disclaimer": ADVISORY_DISCLAIMER,
            "detection_error": detection_error,
        },
        "metadata": {
            "processed_at": _utc_now_iso(),
            "model_used": model_used or None,
            "version": SERVICE_VERSION,
            "source": source_meta.get("source") or ("paper_record" if paper_id is not None else "raw_text"),
            "segment_count": len(heuristics),
            "suspicious_segment_count": len(suspicious_segments),
            "cache_hit": bool(analysis_result.get("cache_hit")),
            "cache_layer": analysis_result.get("cache_layer"),
        },
    }


def _job_input_text(job: PaperCheckJob) -> Optional[str]:
    value = job.input_data.get("text")
    text = str(value or "").strip()
    return text or None


def _job_workspace_id(job: PaperCheckJob) -> Optional[int]:
    raw_value = job.input_data.get("workspace_id")
    if raw_value in (None, ""):
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


async def process_job(
    *,
    repo: ResearchRepository,
    job_id: str,
    worker_id: Optional[str] = None,
    claimed_at: Optional[datetime] = None,
) -> Optional[PaperCheckJob]:
    job = repo.get_paper_check_job(job_id)
    if not job:
        return None
    if job.status == "completed":
        return job
    if job.status != "running":
        return job

    current = repo.get_paper_check_job(job_id)
    if current is None:
        return None
    expected_worker_id = str(worker_id or current.claimed_by or "").strip() or None
    expected_claimed_at = claimed_at or current.claimed_at
    if expected_worker_id and current.claimed_by and current.claimed_by != expected_worker_id:
        return current
    if claimed_at is not None and current.claimed_at and current.claimed_at != claimed_at:
        return current
    if current.result:
        completed = repo.complete_paper_check_job(
            job_id,
            worker_id=expected_worker_id,
            claimed_at=expected_claimed_at,
            result=current.result,
        )
        return completed or repo.get_paper_check_job(job_id)

    result = await run_paper_check(
        repo=repo,
        user_id=int(current.user_id),
        paper_id=current.paper_id,
        raw_text=_job_input_text(current),
        workspace_id=_job_workspace_id(current),
    )
    completed = repo.complete_paper_check_job(
        job_id,
        worker_id=expected_worker_id,
        claimed_at=expected_claimed_at,
        result=result,
    )
    if completed is not None:
        _log_job_event(
            "paper_check_job_completed",
            job_id=job_id,
            worker_id=expected_worker_id,
            latency_ms=completed.latency_ms,
            retry_count=completed.retry_count,
            status=completed.status,
        )
        if completed.latency_ms is not None and completed.latency_ms > HIGH_LATENCY_WARNING_MS:
            logger.warning(
                json.dumps(
                    {
                        "event": "paper_check_job_high_latency",
                        "job_id": job_id,
                        "worker_id": expected_worker_id,
                        "latency_ms": completed.latency_ms,
                        "threshold_ms": HIGH_LATENCY_WARNING_MS,
                    }
                )
            )
    if completed is not None:
        return completed
    return repo.get_paper_check_job(job_id)


def queue_paper_check_job(
    *,
    repo: ResearchRepository,
    user_id: int,
    paper_id: Optional[int],
    raw_text: Optional[str],
    workspace_id: Optional[int],
    priority: Optional[str] = None,
    job_type: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_priority = _normalize_job_priority(priority)
    normalized_job_type = _normalize_job_type(job_type)
    fingerprint = build_job_fingerprint(
        raw_text=raw_text,
        paper_id=paper_id,
        workspace_id=workspace_id,
    )
    reusable = repo.find_reusable_paper_check_job(
        user_id=int(user_id),
        fingerprint=fingerprint,
    )
    if reusable is not None:
        event_name = "paper_check_job_reused_completed" if reusable.status == "completed" and reusable.result else "paper_check_job_deduplicated"
        _log_job_event(
            event_name,
            job_id=reusable.job_id,
            user_id=user_id,
            fingerprint=fingerprint,
            status=reusable.status,
            retry_count=reusable.retry_count,
        )
        if reusable.status == "completed" and reusable.result:
            return {
                "job_id": reusable.job_id,
                "status": "completed",
                "created_at": (reusable.created_at or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z"),
                "updated_at": (reusable.updated_at or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z"),
                "result": reusable.result,
            }
        if reusable.status == "pending":
            target_priority = reusable.priority
            target_job_type = reusable.job_type
            if _JOB_PRIORITY_ORDER[normalized_priority] > _JOB_PRIORITY_ORDER[target_priority]:
                updated = repo.update_paper_check_job(
                    reusable.job_id,
                    {"priority": normalized_priority},
                )
                if updated is not None:
                    reusable = updated
                    target_priority = updated.priority
                    target_job_type = updated.job_type
            _publish_job_trigger(
                reusable.job_id,
                reason="deduplicated_pending",
                priority=target_priority,
                job_type=target_job_type,
                queue_partition=reusable.queue_partition,
            )
        return {
            "job_id": reusable.job_id,
            "status": "pending",
            "created_at": (reusable.created_at or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z"),
            "updated_at": (reusable.updated_at or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z"),
        }

    if MAX_ACTIVE_JOBS_PER_USER > 0:
        active_jobs = repo.count_active_jobs_for_user(int(user_id))
        if active_jobs >= MAX_ACTIVE_JOBS_PER_USER:
            raise ValueError("Too many active paper check jobs. Please wait for existing jobs to finish.")

    job = create_job(
        repo=repo,
        user_id=user_id,
        paper_id=paper_id,
        fingerprint=fingerprint,
        priority=normalized_priority,
        job_type=normalized_job_type,
        raw_text=raw_text,
        workspace_id=workspace_id,
    )
    _log_job_event(
        "paper_check_job_created",
        job_id=job.job_id,
        user_id=user_id,
        fingerprint=fingerprint,
        paper_id=paper_id,
        workspace_id=workspace_id,
        queue_partition=job.queue_partition,
        priority=job.priority,
        job_type=job.job_type,
    )
    _publish_job_trigger(
        job.job_id,
        reason="created",
        priority=job.priority,
        job_type=job.job_type,
        queue_partition=job.queue_partition,
    )
    _warn_on_queue_depth(repo=repo)
    return {
        "job_id": job.job_id,
        "status": job.status,
        "created_at": (job.created_at or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z"),
        "updated_at": (job.updated_at or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z"),
    }


def requeue_failed_job(
    *,
    repo: ResearchRepository,
    job_id: str,
) -> Optional[Dict[str, Any]]:
    job = repo.get_paper_check_job(job_id)
    if job is None:
        return None
    if job.status == "completed":
        raise ValueError("Completed jobs cannot be requeued.")
    if job.status == "running":
        raise ValueError("Running jobs cannot be requeued.")
    if job.status == "failed":
        updated = repo.requeue_paper_check_job(job_id)
    elif job.status == "pending":
        updated = job
    else:
        raise ValueError("Only failed or pending jobs can be requeued.")

    if updated is None:
        return None
    _log_job_event(
        "paper_check_job_admin_requeued",
        job_id=updated.job_id,
        previous_status=job.status,
        retry_count=updated.retry_count,
    )
    _publish_job_trigger(updated.job_id, reason="admin_requeue")
    return _serialize_job(updated)


def get_paper_check_metrics_snapshot(
    *,
    repo: ResearchRepository,
    timeout_seconds: int = JOB_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    return repo.get_paper_check_job_metrics(timeout_seconds)


def _rag_context_for_prompt(
    *,
    repo: ResearchRepository,
    user_id: str,
    workspace_id: Optional[int],
    query: str,
    top_k: int = 6,
    max_context_tokens: int = 1200,
) -> str:
    if workspace_id is None:
        return ""
    try:
        from services.rag_runtime import get_rag_runtime

        runtime = get_rag_runtime(db=getattr(repo, "db", None))
        context = runtime.retrieval_service.retrieve_and_format_sync(
            query=query,
            workspace_id=int(workspace_id),
            top_k=top_k,
            source_types=["paper", "summary", "checker", "report"],
            max_context_tokens=max_context_tokens,
        )
        if context.strip().lower().startswith("no relevant workspace context"):
            return ""
        return context
    except Exception as exc:
        logger.debug(
            "RAG context fetch skipped for workspace_id=%s user_id=%s: %s",
            workspace_id,
            user_id,
            exc,
        )
        return ""


def _index_generated_workspace_artifact(
    *,
    repo: ResearchRepository,
    workspace_id: Optional[int],
    source_id: str,
    source_type: str,
    payload: Dict[str, Any],
    title: Optional[str] = None,
) -> None:
    if workspace_id is None or not payload:
        return
    try:
        from services.rag_index_service import RAGIndexService
        from services.rag_runtime import get_rag_runtime

        runtime = get_rag_runtime(db=getattr(repo, "db", None))
        index_service = RAGIndexService(runtime.embedding_service, runtime.vector_store)

        async def _run() -> None:
            await index_service.index_source(
                workspace_id=int(workspace_id),
                source_id=str(source_id),
                source_type=source_type,
                text=json.dumps(payload, ensure_ascii=False),
                metadata={"title": title or source_type},
            )

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(_run())
        else:
            # Already inside an event loop: skip to avoid nested-loop failures.
            return
    except Exception as exc:
        logger.debug(
            "Generated artifact indexing skipped for workspace_id=%s source_id=%s: %s",
            workspace_id,
            source_id,
            exc,
        )


def aggregate_and_compare_papers(
    *,
    repo: ResearchRepository,
    user_id: str,
    paper_ids: List[int],
    optional_context: Optional[str] = None,
) -> Dict[str, Any]:
    if len(paper_ids) < 2 or len(paper_ids) > 5:
        raise ValueError("You must select between 2 and 5 papers.")

    sorted_pids = sorted(paper_ids)
    fp_base = f"{','.join(map(str, sorted_pids))}|{optional_context or ''}"
    fingerprint = hashlib.sha256(fp_base.encode("utf-8")).hexdigest()

    existing = repo.find_paper_comparison_by_fingerprint(fingerprint)
    if existing and existing.result:
        return existing.result

    context_chunks = []
    workspace_id: Optional[int] = None
    
    for pid in sorted_pids:
        paper = repo.find_paper_for_user(pid, int(user_id))
        if not paper:
            continue
        if workspace_id is None:
            try:
                workspace_id = int(getattr(paper, "workspace_id", 0) or 0) or None
            except Exception:
                workspace_id = None
        
        # Try to find a completed paper check job for this paper
        try:
            from google.cloud.firestore_v1.base_query import FieldFilter
            query = repo.db.collection("paper_check_jobs").where(filter=FieldFilter("paper_id", "==", pid)).where(filter=FieldFilter("status", "==", "completed")).limit(1)
            docs = list(query.stream())
            result_data = docs[0].to_dict().get("result") if docs else None
        except Exception:
            result_data = None
            
        chunk = f"Paper ID: {pid}\nTitle: {paper.title}\nAuthors: {paper.authors}\nAbstract: {paper.abstract}\n"
        
        if result_data:
            key_claims = result_data.get("key_claims", [])
            methods = result_data.get("methodology_summary", "")
            chunk += f"AI Extracted Claims: {json.dumps(key_claims)}\nAI Methods summary: {methods}\n"
            
        context_chunks.append(chunk)

    if len(context_chunks) < 2:
        raise ValueError("Not enough accessible papers to compare.")
    
    papers_context = "\n---\n".join(context_chunks)
    # Truncate to roughly 15000 chars to respect tokens
    papers_context = papers_context[:15000]
    rag_context = _rag_context_for_prompt(
        repo=repo,
        user_id=user_id,
        workspace_id=workspace_id,
        query=optional_context
        or "Compare these papers and identify major agreements, contradictions, and methodological differences.",
        top_k=6,
        max_context_tokens=1000,
    )
    if rag_context:
        papers_context = f"{papers_context}\n\n## Workspace Retrieval Context\n{rag_context}"
    
    from services.ai_service import compare_papers_task
    ai_result = compare_papers_task(
        groq_client=groq_client,
        db=repo.db,
        user_id=str(user_id),
        papers_context=papers_context,
        optional_context=optional_context,
    )
    
    if ai_result.get("error") and not ai_result.get("parsed"):
        raise RuntimeError(f"AI Comparison Failed: {ai_result['error']}")

    result_data = ai_result.get("parsed") or {}
    comparison_id = uuid4().hex

    repo.create_paper_comparison(
        id=comparison_id,
        user_id=int(user_id),
        paper_ids=sorted_pids,
        optional_context=optional_context,
        fingerprint=fingerprint,
        result=result_data,
    )
    _index_generated_workspace_artifact(
        repo=repo,
        workspace_id=workspace_id,
        source_id=comparison_id,
        source_type="summary",
        payload=result_data,
        title="Paper comparison output",
    )
    if workspace_id is not None:
        try:
            from services.workspace_feed_service import queue_workspace_feed_job_best_effort
            from services.workspace_insights_service import queue_workspace_insights_job_best_effort

            queue_workspace_insights_job_best_effort(
                repo=repo,
                workspace_id=int(workspace_id),
                user_id=int(user_id),
                trigger="comparison_generated",
                reason=f"comparison:{comparison_id}",
            )
            queue_workspace_feed_job_best_effort(
                repo=repo,
                workspace_id=int(workspace_id),
                user_id=int(user_id),
                trigger="comparison_generated",
                reason=f"comparison:{comparison_id}",
            )
        except Exception:
            pass
    
    return result_data


def aggregate_and_generate_report(
    *,
    repo: ResearchRepository,
    user_id: str,
    paper_ids: List[int],
    topic: Optional[str] = None,
) -> Dict[str, Any]:
    sorted_pids = sorted(paper_ids)
    fp_base = f"{','.join(map(str, sorted_pids))}|{topic or ''}"
    fingerprint = hashlib.sha256(fp_base.encode("utf-8")).hexdigest()

    existing = repo.find_research_report_by_fingerprint(fingerprint)
    if existing and existing.result:
        return existing.result

    context_chunks = []
    workspace_id: Optional[int] = None
    
    for pid in sorted_pids:
        paper = repo.find_paper_for_user(pid, int(user_id))
        if not paper:
            continue
        if workspace_id is None:
            try:
                workspace_id = int(getattr(paper, "workspace_id", 0) or 0) or None
            except Exception:
                workspace_id = None
        result_data = None
        db = getattr(repo, "db", None)
        if db is not None:
            try:
                from google.cloud.firestore_v1.base_query import FieldFilter

                query = (
                    db.collection("paper_check_jobs")
                    .where(filter=FieldFilter("paper_id", "==", pid))
                    .where(filter=FieldFilter("status", "==", "completed"))
                    .limit(1)
                )
                docs = list(query.stream())
                result_data = docs[0].to_dict().get("result") if docs else None
            except Exception:
                result_data = None
            
        chunk = f"Paper ID: {pid}\nTitle: {paper.title}\nAuthors: {paper.authors}\nAbstract: {paper.abstract}\n"
        
        if result_data:
            # Prefer the newer checker schema if present; fall back to legacy keys.
            snapshot = result_data.get("paper_analysis", {}).get("snapshot", {}) if isinstance(result_data, dict) else {}
            summary = snapshot.get("summary") if isinstance(snapshot, dict) else None
            claims = result_data.get("paper_analysis", {}).get("claims", []) if isinstance(result_data, dict) else []
            methods_obj = result_data.get("paper_analysis", {}).get("methods", {}) if isinstance(result_data, dict) else {}
            methods_summary = methods_obj.get("approach") if isinstance(methods_obj, dict) else None

            legacy_claims = result_data.get("key_claims", []) if isinstance(result_data, dict) else []
            legacy_methods = result_data.get("methodology_summary", "") if isinstance(result_data, dict) else ""

            chunk += "AI Checker Outputs:\n"
            if summary:
                chunk += f"- Summary: {str(summary)[:1500]}\n"
            if claims:
                chunk += f"- Claims: {json.dumps(claims)[:2500]}\n"
            if methods_summary:
                chunk += f"- Methodology: {str(methods_summary)[:1200]}\n"
            if legacy_claims and not claims:
                chunk += f"- Legacy Claims: {json.dumps(legacy_claims)[:2500]}\n"
            if legacy_methods and not methods_summary:
                chunk += f"- Legacy Methods: {str(legacy_methods)[:1200]}\n"
            
        context_chunks.append(chunk)

    if not context_chunks and not topic:
        raise ValueError("You must provide either papers or a topic to generate a report.")
    
    papers_context = "\n---\n".join(context_chunks)
    papers_context = papers_context[:25000]
    rag_context = _rag_context_for_prompt(
        repo=repo,
        user_id=user_id,
        workspace_id=workspace_id,
        query=topic
        or "Summarize workspace trends, contradictions, and high-impact gaps across the indexed research.",
        top_k=8,
        max_context_tokens=1400,
    )
    if rag_context:
        papers_context = f"{papers_context}\n\n## Workspace Retrieval Context\n{rag_context}"
    
    from services.ai_service import generate_research_report_task
    ai_result = generate_research_report_task(
        groq_client=groq_client,
        db=repo.db,
        user_id=str(user_id),
        context=papers_context,
        topic=topic,
    )
    
    if ai_result.get("error") and not ai_result.get("parsed"):
        raise RuntimeError(f"AI Report Generation Failed: {ai_result['error']}")

    result_data = ai_result.get("parsed") or {}

    report_id = uuid4().hex
    repo.create_research_report(
        id=report_id,
        user_id=int(user_id),
        paper_ids=sorted_pids,
        topic=topic,
        fingerprint=fingerprint,
        result=result_data,
    )
    _index_generated_workspace_artifact(
        repo=repo,
        workspace_id=workspace_id,
        source_id=report_id,
        source_type="report",
        payload=result_data,
        title=topic or "Research report output",
    )
    if workspace_id is not None:
        try:
            from services.workspace_feed_service import queue_workspace_feed_job_best_effort
            from services.workspace_insights_service import queue_workspace_insights_job_best_effort

            queue_workspace_insights_job_best_effort(
                repo=repo,
                workspace_id=int(workspace_id),
                user_id=int(user_id),
                trigger="report_generated",
                reason=f"report:{report_id}",
            )
            queue_workspace_feed_job_best_effort(
                repo=repo,
                workspace_id=int(workspace_id),
                user_id=int(user_id),
                trigger="report_generated",
                reason=f"report:{report_id}",
            )
        except Exception:
            pass
    
    return result_data
