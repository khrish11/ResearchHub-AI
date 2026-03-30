from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import uuid4

from google.cloud.firestore_v1.base_query import FieldFilter

from repositories import ResearchRepository
from services.ai_service import run_structured_json_task
from services.rag_runtime import get_rag_runtime
from utils.groq_client import client as groq_client


logger = logging.getLogger(__name__)

WORKSPACE_INSIGHTS_TASK_TYPE = "workspace_insights"
WORKSPACE_INSIGHTS_DISCLAIMER = (
    "Insights are AI-generated summaries from workspace evidence and may be incomplete. "
    "Always verify by opening linked sources."
)
INSIGHT_SECTION_KEYS: Tuple[str, ...] = (
    "key_themes",
    "emerging_trends",
    "contradictions",
    "important_findings",
    "research_gaps",
    "recommended_next_steps",
)
SECTION_TEXT_KEYS: Dict[str, Tuple[str, ...]] = {
    "key_themes": ("theme", "title", "text", "item", "statement"),
    "emerging_trends": ("trend", "title", "text", "item", "statement"),
    "contradictions": ("contradiction", "statement", "text", "item"),
    "important_findings": ("finding", "statement", "text", "item"),
    "research_gaps": ("gap", "statement", "text", "item"),
    "recommended_next_steps": ("step", "action", "text", "item", "statement"),
}
DEFAULT_CACHE_HOURS = max(
    1,
    int(os.getenv("WORKSPACE_INSIGHTS_CACHE_HOURS", "6") or 6),
)
DEFAULT_TOP_K = max(
    4,
    int(os.getenv("WORKSPACE_INSIGHTS_TOP_K", "5") or 5),
)
DEFAULT_MAX_CONTEXT_TOKENS = max(
    500,
    int(os.getenv("WORKSPACE_INSIGHTS_MAX_CONTEXT_TOKENS", "2200") or 2200),
)
DEFAULT_MAX_ITEMS_PER_SECTION = max(
    3,
    int(os.getenv("WORKSPACE_INSIGHTS_MAX_ITEMS_PER_SECTION", "7") or 7),
)
MAX_PROCESSING_SECONDS = max(
    30,
    int(os.getenv("WORKSPACE_INSIGHTS_TIMEOUT_SECONDS", "180") or 180),
)
JOB_STUCK_TIMEOUT_SECONDS = max(
    MAX_PROCESSING_SECONDS,
    int(os.getenv("WORKSPACE_INSIGHTS_STUCK_TIMEOUT_SECONDS", str(MAX_PROCESSING_SECONDS)) or MAX_PROCESSING_SECONDS),
)
_SOURCE_REF_RE = re.compile(r"\d+")

_IN_MEMORY_LOCK = Lock()
_IN_MEMORY_INSIGHTS: Dict[str, Dict[str, Any]] = {}
_IN_MEMORY_JOBS: Dict[str, Dict[str, Any]] = {}


def _log_job_event(event: str, **fields: Any) -> None:
    logger.info(json.dumps({"event": event, **fields}, default=str))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        parsed = value.strip()
        if not parsed:
            return None
        try:
            if parsed.endswith("Z"):
                parsed = parsed[:-1] + "+00:00"
            dt = datetime.fromisoformat(parsed)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None
    return None


def _to_iso(value: Any) -> str:
    dt = _as_datetime(value) or _utcnow()
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _collection(repo: ResearchRepository, name: str):  # type: ignore[no-untyped-def]
    db = getattr(repo, "db", None)
    if db is None:
        return None
    try:
        return db.collection(name)
    except Exception:
        return None


def _resolve_workspace_owner_user_id(
    *,
    repo: ResearchRepository,
    workspace_id: int,
) -> Optional[int]:
    db = getattr(repo, "db", None)
    if db is not None:
        try:
            snapshot = db.collection("workspaces").document(str(int(workspace_id))).get()
            if snapshot.exists:
                payload = snapshot.to_dict() or {}
                owner_id = _coerce_int(payload.get("user_id"), 0)
                return owner_id if owner_id > 0 else None
        except Exception:
            return None
    workspaces_map = getattr(repo, "_workspaces", None)
    if isinstance(workspaces_map, dict):
        ws = workspaces_map.get(int(workspace_id))
        owner = _coerce_int(getattr(ws, "user_id", 0), 0)
        return owner if owner > 0 else None
    return None


def _list_insight_docs(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: int,
) -> List[Dict[str, Any]]:
    collection = _collection(repo, "workspace_insights")
    docs: List[Dict[str, Any]] = []
    if collection is not None:
        try:
            query = (
                collection.where(
                    filter=FieldFilter("workspace_id", "==", int(workspace_id))
                ).where(
                    filter=FieldFilter("user_id", "==", int(user_id))
                )
            )
            try:
                snapshots = query.order_by("generated_at", direction="DESCENDING").limit(50).stream()
            except Exception:
                snapshots = query.stream()
        except Exception:
            snapshots = []
        for snapshot in snapshots:
            payload = snapshot.to_dict() or {}
            docs.append(payload)
    else:
        with _IN_MEMORY_LOCK:
            for payload in _IN_MEMORY_INSIGHTS.values():
                if _coerce_int(payload.get("workspace_id"), 0) != int(workspace_id):
                    continue
                if _coerce_int(payload.get("user_id"), 0) != int(user_id):
                    continue
                docs.append(dict(payload))
    docs.sort(
        key=lambda row: _as_datetime(row.get("generated_at"))
        or _as_datetime(row.get("updated_at"))
        or _utcnow(),
        reverse=True,
    )
    return docs


def _persist_insight(
    *,
    repo: ResearchRepository,
    payload: Dict[str, Any],
    merge: bool = False,
) -> None:
    insight_id = _safe_str(payload.get("insight_id"))
    if not insight_id:
        raise ValueError("insight_id is required")
    collection = _collection(repo, "workspace_insights")
    if collection is not None:
        collection.document(insight_id).set(payload, merge=bool(merge))
        return
    with _IN_MEMORY_LOCK:
        existing = _IN_MEMORY_INSIGHTS.get(insight_id, {})
        if merge:
            merged = dict(existing)
            merged.update(payload)
            _IN_MEMORY_INSIGHTS[insight_id] = merged
        else:
            _IN_MEMORY_INSIGHTS[insight_id] = dict(payload)


def get_latest_workspace_insights(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: int,
) -> Optional[Dict[str, Any]]:
    rows = _list_insight_docs(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    return rows[0] if rows else None


def _touch_insight_expiry(
    *,
    repo: ResearchRepository,
    insight: Dict[str, Any],
    cache_hours: int,
) -> Dict[str, Any]:
    now = _utcnow()
    insight_id = _safe_str(insight.get("insight_id"))
    if not insight_id:
        return insight
    updated = {
        "insight_id": insight_id,
        "expires_at": now + timedelta(hours=max(1, int(cache_hours))),
        "updated_at": now,
    }
    _persist_insight(repo=repo, payload=updated, merge=True)
    merged = dict(insight)
    merged.update(updated)
    return merged


def _list_jobs(
    *,
    repo: ResearchRepository,
    workspace_id: Optional[int] = None,
    statuses: Optional[Sequence[str]] = None,
    user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    collection = _collection(repo, "workspace_insight_jobs")
    status_set = {str(item).lower() for item in (statuses or [])}
    docs: List[Dict[str, Any]] = []
    if collection is not None:
        query = collection
        if workspace_id is not None:
            query = query.where(
                filter=FieldFilter("workspace_id", "==", int(workspace_id))
            )
        if user_id is not None:
            query = query.where(
                filter=FieldFilter("user_id", "==", int(user_id))
            )
        try:
            snapshots = query.order_by("created_at").stream()
        except Exception:
            snapshots = query.stream()
        for snapshot in snapshots:
            payload = snapshot.to_dict() or {}
            if workspace_id is not None and _coerce_int(payload.get("workspace_id"), 0) != int(workspace_id):
                continue
            if user_id is not None and _coerce_int(payload.get("user_id"), 0) != int(user_id):
                continue
            status = _safe_str(payload.get("status")).lower()
            if status_set and status not in status_set:
                continue
            docs.append(payload)
    else:
        with _IN_MEMORY_LOCK:
            for payload in _IN_MEMORY_JOBS.values():
                if workspace_id is not None and _coerce_int(payload.get("workspace_id"), 0) != int(workspace_id):
                    continue
                if user_id is not None and _coerce_int(payload.get("user_id"), 0) != int(user_id):
                    continue
                status = _safe_str(payload.get("status")).lower()
                if status_set and status not in status_set:
                    continue
                docs.append(dict(payload))
    docs.sort(
        key=lambda row: _as_datetime(row.get("created_at")) or _utcnow(),
        reverse=False,
    )
    return docs


def _persist_job(
    *,
    repo: ResearchRepository,
    payload: Dict[str, Any],
    merge: bool = False,
) -> None:
    job_id = _safe_str(payload.get("job_id"))
    if not job_id:
        raise ValueError("job_id is required")
    collection = _collection(repo, "workspace_insight_jobs")
    if collection is not None:
        collection.document(job_id).set(payload, merge=bool(merge))
        return
    with _IN_MEMORY_LOCK:
        existing = _IN_MEMORY_JOBS.get(job_id, {})
        if merge:
            merged = dict(existing)
            merged.update(payload)
            _IN_MEMORY_JOBS[job_id] = merged
        else:
            _IN_MEMORY_JOBS[job_id] = dict(payload)


def get_workspace_insights_job(
    *,
    repo: ResearchRepository,
    job_id: str,
) -> Optional[Dict[str, Any]]:
    target = _safe_str(job_id)
    if not target:
        return None
    collection = _collection(repo, "workspace_insight_jobs")
    if collection is not None:
        snapshot = collection.document(target).get()
        if not snapshot.exists:
            return None
        return snapshot.to_dict() or {}
    with _IN_MEMORY_LOCK:
        payload = _IN_MEMORY_JOBS.get(target)
        return dict(payload) if payload else None


def list_pending_workspace_insight_jobs(
    *,
    repo: ResearchRepository,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    jobs = _list_jobs(repo=repo, statuses=("pending",))
    return jobs[: max(1, int(limit))]


def list_stuck_workspace_insight_jobs(
    *,
    repo: ResearchRepository,
    timeout_seconds: int = JOB_STUCK_TIMEOUT_SECONDS,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    cutoff = _utcnow() - timedelta(seconds=max(10, int(timeout_seconds or JOB_STUCK_TIMEOUT_SECONDS)))
    running = _list_jobs(repo=repo, statuses=("running",))
    stuck: List[Dict[str, Any]] = []
    for row in running:
        started = (
            _as_datetime(row.get("processing_started_at"))
            or _as_datetime(row.get("claimed_at"))
            or _as_datetime(row.get("updated_at"))
        )
        if started is None or started > cutoff:
            continue
        stuck.append(row)
        if len(stuck) >= max(1, int(limit)):
            break
    return stuck


def recover_stuck_workspace_insight_jobs(
    *,
    repo: ResearchRepository,
    timeout_seconds: int = JOB_STUCK_TIMEOUT_SECONDS,
    limit: int = 50,
) -> int:
    recovered = 0
    for row in list_stuck_workspace_insight_jobs(
        repo=repo,
        timeout_seconds=timeout_seconds,
        limit=limit,
    ):
        job_id = _safe_str(row.get("job_id"))
        if not job_id:
            continue
        updated = _fail_job(
            repo=repo,
            job_id=job_id,
            error_message=f"Recovered stale running job after {int(timeout_seconds)}s.",
        )
        if updated and _safe_str(updated.get("status")).lower() == "pending":
            recovered += 1
    if recovered > 0:
        _log_job_event(
            "workspace_insights_stuck_jobs_recovered",
            recovered=recovered,
            timeout_seconds=int(timeout_seconds),
        )
    return recovered


def _find_active_job_for_fingerprint(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: int,
    fingerprint: str,
) -> Optional[Dict[str, Any]]:
    jobs = _list_jobs(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
        statuses=("pending", "running"),
    )
    for job in jobs:
        if _safe_str(job.get("fingerprint")) == str(fingerprint):
            return job
    return None


def _extract_workspace_id_from_job_input(payload: Dict[str, Any]) -> Optional[int]:
    input_blob = payload.get("input")
    if not isinstance(input_blob, dict):
        input_blob = payload.get("input_data")
    if not isinstance(input_blob, dict):
        return None
    raw_workspace = input_blob.get("workspace_id")
    workspace_id = _coerce_int(raw_workspace, 0)
    return workspace_id if workspace_id > 0 else None


def build_workspace_state_fingerprint(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: int,
) -> Tuple[str, Dict[str, Any]]:
    papers = repo.list_papers_for_workspace(int(workspace_id))
    paper_ids = sorted(int(paper.id) for paper in papers)
    paper_id_set = set(paper_ids)
    basis: Dict[str, Any] = {
        "workspace_id": int(workspace_id),
        "user_id": int(user_id),
        "papers": [
            {
                "id": int(paper.id),
                "title": _safe_str(getattr(paper, "title", ""))[:180],
                "doi": _safe_str(getattr(paper, "doi", ""))[:120],
                "url": _safe_str(getattr(paper, "url", ""))[:200],
            }
            for paper in sorted(papers, key=lambda row: int(row.id))
        ],
        "reports": [],
        "comparisons": [],
        "checker_jobs": [],
    }
    db = getattr(repo, "db", None)
    if db is not None:
        try:
            report_docs = db.collection("research_reports").where(
                filter=FieldFilter("user_id", "==", int(user_id))
            ).stream()
        except Exception:
            report_docs = []
        for snapshot in report_docs:
            row = snapshot.to_dict() or {}
            report_pids = {
                _coerce_int(value, 0)
                for value in (row.get("paper_ids") or [])
                if _coerce_int(value, 0) > 0
            }
            if report_pids and report_pids.isdisjoint(paper_id_set):
                continue
            basis["reports"].append(
                {
                    "id": _safe_str(row.get("id") or snapshot.id),
                    "fingerprint": _safe_str(row.get("fingerprint")),
                    "created_at": _to_iso(row.get("created_at")),
                }
            )
        try:
            compare_docs = db.collection("paper_comparisons").where(
                filter=FieldFilter("user_id", "==", int(user_id))
            ).stream()
        except Exception:
            compare_docs = []
        for snapshot in compare_docs:
            row = snapshot.to_dict() or {}
            compare_pids = {
                _coerce_int(value, 0)
                for value in (row.get("paper_ids") or [])
                if _coerce_int(value, 0) > 0
            }
            if compare_pids and compare_pids.isdisjoint(paper_id_set):
                continue
            basis["comparisons"].append(
                {
                    "id": _safe_str(row.get("id") or snapshot.id),
                    "fingerprint": _safe_str(row.get("fingerprint")),
                    "created_at": _to_iso(row.get("created_at")),
                }
            )
        try:
            checker_docs = (
                db.collection("paper_check_jobs")
                .where(filter=FieldFilter("status", "==", "completed"))
                .where(filter=FieldFilter("user_id", "==", int(user_id)))
                .stream()
            )
        except Exception:
            checker_docs = []
        for snapshot in checker_docs:
            row = snapshot.to_dict() or {}
            job_workspace_id = _extract_workspace_id_from_job_input(row)
            paper_id = _coerce_int(row.get("paper_id"), 0)
            if job_workspace_id != int(workspace_id) and paper_id not in paper_id_set:
                continue
            basis["checker_jobs"].append(
                {
                    "job_id": _safe_str(row.get("job_id") or snapshot.id),
                    "paper_id": paper_id if paper_id > 0 else None,
                    "updated_at": _to_iso(row.get("updated_at")),
                }
            )

    basis["reports"].sort(key=lambda row: (row.get("id") or "", row.get("created_at") or ""))
    basis["comparisons"].sort(key=lambda row: (row.get("id") or "", row.get("created_at") or ""))
    basis["checker_jobs"].sort(key=lambda row: (row.get("job_id") or "", row.get("updated_at") or ""))
    serialized = json.dumps(basis, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return digest, basis


def _claim_job(
    *,
    repo: ResearchRepository,
    job_id: str,
    worker_id: str,
) -> Optional[Dict[str, Any]]:
    current = get_workspace_insights_job(repo=repo, job_id=job_id)
    if not current:
        return None
    now = _utcnow()
    current_status = _safe_str(current.get("status")).lower()
    if current_status == "running" and _safe_str(current.get("claimed_by")) == _safe_str(worker_id):
        return current
    if current_status == "running":
        started = (
            _as_datetime(current.get("processing_started_at"))
            or _as_datetime(current.get("claimed_at"))
            or _as_datetime(current.get("updated_at"))
        )
        if started and (now - started).total_seconds() > JOB_STUCK_TIMEOUT_SECONDS:
            _persist_job(
                repo=repo,
                payload={
                    "job_id": _safe_str(job_id),
                    "status": "pending",
                    "claimed_by": None,
                    "claimed_at": None,
                    "processing_started_at": None,
                    "updated_at": now,
                    "error": "Recovered stale running job.",
                },
                merge=True,
            )
            _log_job_event(
                "workspace_insights_job_recovered",
                job_id=_safe_str(job_id),
                stale_seconds=round((now - started).total_seconds(), 3),
            )
            current = get_workspace_insights_job(repo=repo, job_id=job_id) or current
            current_status = _safe_str(current.get("status")).lower()
    if current_status != "pending":
        return None
    updates = {
        "job_id": _safe_str(job_id),
        "status": "running",
        "claimed_by": _safe_str(worker_id),
        "claimed_at": now,
        "processing_started_at": current.get("processing_started_at") or now,
        "updated_at": now,
    }
    _persist_job(repo=repo, payload=updates, merge=True)
    _log_job_event(
        "workspace_insights_job_transition",
        job_id=_safe_str(job_id),
        status="running",
        worker_id=_safe_str(worker_id),
    )
    return get_workspace_insights_job(repo=repo, job_id=job_id)


def _complete_job(
    *,
    repo: ResearchRepository,
    job_id: str,
    result: Dict[str, Any],
    processing_started_at: Any,
) -> Optional[Dict[str, Any]]:
    now = _utcnow()
    started = _as_datetime(processing_started_at) or now
    latency_ms = max(0, int((now - started).total_seconds() * 1000))
    updates = {
        "job_id": _safe_str(job_id),
        "status": "completed",
        "result": dict(result or {}),
        "error": None,
        "processing_completed_at": now,
        "latency_ms": latency_ms,
        "updated_at": now,
    }
    _persist_job(repo=repo, payload=updates, merge=True)
    _log_job_event(
        "workspace_insights_job_transition",
        job_id=_safe_str(job_id),
        status="completed",
        latency_ms=latency_ms,
    )
    return get_workspace_insights_job(repo=repo, job_id=job_id)


def _fail_job(
    *,
    repo: ResearchRepository,
    job_id: str,
    error_message: str,
) -> Optional[Dict[str, Any]]:
    current = get_workspace_insights_job(repo=repo, job_id=job_id) or {}
    now = _utcnow()
    retry_count = _coerce_int(current.get("retry_count"), 0)
    max_retries = max(0, _coerce_int(current.get("max_retries"), 1))
    next_retry_count = retry_count + 1
    should_retry = next_retry_count <= max_retries
    started = _as_datetime(current.get("processing_started_at"))
    latency_ms = max(0, int((now - started).total_seconds() * 1000)) if started else None

    updates: Dict[str, Any] = {
        "job_id": _safe_str(job_id),
        "error": _safe_str(error_message)[:1200] or "Workspace insights job failed.",
        "retry_count": next_retry_count,
        "claimed_by": None,
        "claimed_at": None,
        "updated_at": now,
    }
    if should_retry:
        updates.update(
            {
                "status": "pending",
                "processing_started_at": None,
                "processing_completed_at": None,
            }
        )
    else:
        updates.update(
            {
                "status": "failed",
                "processing_completed_at": now,
            }
        )
        if latency_ms is not None:
            updates["latency_ms"] = latency_ms
    _persist_job(repo=repo, payload=updates, merge=True)
    _log_job_event(
        "workspace_insights_job_transition",
        job_id=_safe_str(job_id),
        status=_safe_str(updates.get("status")),
        retry_count=next_retry_count,
        max_retries=max_retries,
        latency_ms=latency_ms,
    )
    return get_workspace_insights_job(repo=repo, job_id=job_id)


def _normalize_refs(value: Any, *, max_source_index: int) -> List[int]:
    values: List[int] = []
    if isinstance(value, list):
        candidates = value
    elif isinstance(value, tuple):
        candidates = list(value)
    elif isinstance(value, str):
        candidates = [int(token) for token in _SOURCE_REF_RE.findall(value)]
    elif isinstance(value, (int, float)):
        candidates = [int(value)]
    else:
        candidates = []
    for candidate in candidates:
        idx = _coerce_int(candidate, 0)
        if idx < 1 or idx > max_source_index:
            continue
        if idx not in values:
            values.append(idx)
    return values


def _extract_item_text(entry: Dict[str, Any], section_key: str) -> str:
    for key in SECTION_TEXT_KEYS.get(section_key, ("text", "item", "statement")):
        value = _safe_str(entry.get(key))
        if value:
            return value
    return _safe_str(entry.get("text")) or _safe_str(entry.get("item")) or _safe_str(entry.get("statement"))


def normalize_workspace_insights_payload(
    *,
    parsed_payload: Any,
    max_source_index: int,
    max_items_per_section: int = DEFAULT_MAX_ITEMS_PER_SECTION,
) -> Dict[str, List[Dict[str, Any]]]:
    parsed = parsed_payload if isinstance(parsed_payload, dict) else {}
    output: Dict[str, List[Dict[str, Any]]] = {}
    max_items = max(1, int(max_items_per_section))
    for section_key in INSIGHT_SECTION_KEYS:
        raw_value = parsed.get(section_key)
        if isinstance(raw_value, list):
            entries = raw_value
        elif isinstance(raw_value, dict):
            entries = [raw_value]
        elif isinstance(raw_value, str):
            entries = [raw_value]
        else:
            entries = []
        normalized_rows: List[Dict[str, Any]] = []
        for entry in entries:
            text = ""
            refs: List[int] = []
            if isinstance(entry, str):
                text = _safe_str(entry)
            elif isinstance(entry, dict):
                text = _extract_item_text(entry, section_key)
                refs = _normalize_refs(
                    entry.get("source_refs")
                    or entry.get("sources")
                    or entry.get("source_indexes")
                    or entry.get("evidence"),
                    max_source_index=max_source_index,
                )
            else:
                text = _safe_str(entry)
            if not text:
                continue
            normalized_rows.append(
                {
                    "text": text[:420],
                    "source_refs": refs,
                }
            )
            if len(normalized_rows) >= max_items:
                break
        output[section_key] = normalized_rows
    return output


def _extract_source_refs_from_payload(payload: Dict[str, Any]) -> List[int]:
    refs: List[int] = []
    for key in INSIGHT_SECTION_KEYS:
        for item in payload.get(key, []):
            if not isinstance(item, dict):
                continue
            for ref in item.get("source_refs") or []:
                idx = _coerce_int(ref, 0)
                if idx > 0 and idx not in refs:
                    refs.append(idx)
    return refs


def _build_sources_catalog(
    *,
    context_rows: Sequence[Dict[str, Any]],
    only_refs: Optional[Sequence[int]] = None,
) -> List[Dict[str, Any]]:
    ref_set = {int(item) for item in (only_refs or []) if _coerce_int(item, 0) > 0}
    sources: List[Dict[str, Any]] = []
    for row in context_rows:
        source_index = _coerce_int(row.get("source_index"), 0)
        if ref_set and source_index not in ref_set:
            continue
        metadata = row.get("metadata") or {}
        sources.append(
            {
                "source_index": source_index,
                "source_id": _safe_str(row.get("source_id")),
                "source_type": _safe_str(row.get("source_type")) or "unknown",
                "title": _safe_str(metadata.get("title")) or "Untitled",
                "similarity_score": round(float(row.get("similarity_score") or 0.0), 4),
                "url": _safe_str(metadata.get("url")),
                "doi": _safe_str(metadata.get("doi")),
            }
        )
    sources.sort(key=lambda item: int(item.get("source_index") or 0))
    return sources


def _calculate_confidence(
    *,
    normalized_payload: Dict[str, List[Dict[str, Any]]],
    context_rows: Sequence[Dict[str, Any]],
) -> float:
    total_items = sum(len(normalized_payload.get(key, [])) for key in INSIGHT_SECTION_KEYS)
    if total_items <= 0 or not context_rows:
        return 0.0
    refs = _extract_source_refs_from_payload(normalized_payload)
    used_rows = {
        _coerce_int(row.get("source_index"), 0): row
        for row in context_rows
        if _coerce_int(row.get("source_index"), 0) > 0
    }
    used_similarities = [
        float(used_rows[idx].get("similarity_score") or 0.0)
        for idx in refs
        if idx in used_rows
    ]
    if not used_similarities:
        used_similarities = [float(row.get("similarity_score") or 0.0) for row in context_rows]
    avg_similarity = sum(used_similarities) / max(1, len(used_similarities))
    source_coverage = len(refs) / max(1, len(context_rows))
    section_coverage = (
        sum(1 for key in INSIGHT_SECTION_KEYS if normalized_payload.get(key)) / float(len(INSIGHT_SECTION_KEYS))
    )
    confidence = (0.4 * min(1.0, source_coverage)) + (0.35 * min(1.0, avg_similarity)) + (0.25 * section_coverage)
    return round(max(0.0, min(1.0, confidence)), 4)


def _insights_system_prompt() -> str:
    return (
        "You are Soyog AI's autonomous workspace analyst.\n"
        "Generate proactive insights ONLY from provided workspace context.\n"
        "Never invent sources, papers, metrics, or contradictions.\n"
        "Every item should include source_refs with source index numbers.\n"
        "If evidence is weak, keep lists short and explicit.\n"
        "Return strict JSON only."
    )


def _insights_user_prompt(
    *,
    context_rows: Sequence[Dict[str, Any]],
) -> str:
    if not context_rows:
        context_blob = "No workspace evidence available."
    else:
        lines: List[str] = ["## Retrieved Workspace Sources"]
        for row in context_rows:
            metadata = row.get("metadata") or {}
            lines.extend(
                [
                    f"### Source {row.get('source_index')}",
                    f"- source_id: {_safe_str(row.get('source_id'))}",
                    f"- source_type: {_safe_str(row.get('source_type'))}",
                    f"- title: {_safe_str(metadata.get('title')) or 'Untitled'}",
                    f"- similarity: {float(row.get('similarity_score') or 0.0):.3f}",
                    _safe_str(row.get("text"))[:2500],
                ]
            )
        context_blob = "\n".join(lines)
    schema = (
        "{\n"
        '  "key_themes": [{"theme": "string", "source_refs": [1]}],\n'
        '  "emerging_trends": [{"trend": "string", "source_refs": [1]}],\n'
        '  "contradictions": [{"contradiction": "string", "source_refs": [1,2]}],\n'
        '  "important_findings": [{"finding": "string", "source_refs": [1]}],\n'
        '  "research_gaps": [{"gap": "string", "source_refs": [1]}],\n'
        '  "recommended_next_steps": [{"step": "string", "source_refs": [1]}]\n'
        "}"
    )
    return (
        f"{context_blob}\n\n"
        "Generate dashboard-ready insights for this workspace.\n"
        "Constraints:\n"
        "- Keep each insight concise and actionable.\n"
        "- Use 0-7 items per section.\n"
        "- source_refs must reference available Source numbers only.\n"
        "- If no evidence, return empty arrays for that section.\n\n"
        f"Output schema:\n{schema}"
    )


async def _build_context_rows(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    top_k: int,
    max_context_tokens: int,
) -> List[Dict[str, Any]]:
    runtime = get_rag_runtime(db=getattr(repo, "db", None))
    source_types = ["summary", "report", "checker", "paper"]
    retrieval_queries = [
        "Key themes and recurring concepts in this workspace",
        "Emerging trends and novel methods in recent papers",
        "Contradictions, disagreements, and conflicting results",
        "Important findings, limitations, and open research gaps",
        "Recommended next research steps from workspace evidence",
    ]
    by_vector_id: Dict[str, Any] = {}
    for query in retrieval_queries:
        rows = await runtime.retrieval_service.retrieve(
            query=query,
            workspace_id=int(workspace_id),
            top_k=max(3, int(top_k)),
            source_types=source_types,
            min_similarity=0.3,
        )
        for row in rows:
            existing = by_vector_id.get(row.vector_id)
            if existing is None or float(row.similarity_score) > float(existing.similarity_score):
                by_vector_id[row.vector_id] = row
    candidates = list(by_vector_id.values())
    candidates.sort(
        key=lambda row: float(row.similarity_score),
        reverse=True,
    )
    trimmed = runtime.retrieval_service.truncate_results_for_context(
        candidates,
        max_context_tokens=max(500, int(max_context_tokens)),
    )
    context_rows: List[Dict[str, Any]] = []
    for index, row in enumerate(trimmed, start=1):
        context_rows.append(
            {
                "source_index": index,
                "vector_id": row.vector_id,
                "source_id": row.source_id,
                "source_type": row.source_type,
                "text": row.text,
                "similarity_score": float(row.similarity_score),
                "metadata": dict(row.metadata or {}),
            }
        )
    return context_rows


def _run_workspace_insights_model(
    *,
    repo: ResearchRepository,
    user_id: int,
    context_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    response = run_structured_json_task(
        groq_client=groq_client,
        db=getattr(repo, "db", None),
        user_id=str(int(user_id)),
        task_type=WORKSPACE_INSIGHTS_TASK_TYPE,
        query=_insights_user_prompt(context_rows=context_rows),
        system_prompt=_insights_system_prompt(),
        cacheable=False,
        timeout_seconds=MAX_PROCESSING_SECONDS,
        model_overrides={"response_format": {"type": "json_object"}},
        max_attempts=2,
    )
    if response.get("error") and response.get("parsed") is None:
        raise RuntimeError(_safe_str(response.get("error")) or "Workspace insights generation failed.")
    parsed = response.get("parsed")
    return parsed if isinstance(parsed, dict) else {}


def enqueue_workspace_insights_job(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: Optional[int] = None,
    trigger: str = "manual_refresh",
    force: bool = False,
    reason: Optional[str] = None,
    top_k: Optional[int] = None,
    max_context_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    workspace_id = int(workspace_id)
    resolved_user_id = int(user_id or 0)
    if resolved_user_id <= 0:
        owner = _resolve_workspace_owner_user_id(repo=repo, workspace_id=workspace_id)
        resolved_user_id = int(owner or 0)
    if workspace_id <= 0 or resolved_user_id <= 0:
        raise ValueError("workspace_id and user_id are required to enqueue workspace insights job.")

    cache_hours = DEFAULT_CACHE_HOURS
    now = _utcnow()
    fingerprint, fingerprint_basis = build_workspace_state_fingerprint(
        repo=repo,
        workspace_id=workspace_id,
        user_id=resolved_user_id,
    )
    latest = get_latest_workspace_insights(
        repo=repo,
        workspace_id=workspace_id,
        user_id=resolved_user_id,
    )
    if latest and _safe_str(latest.get("fingerprint")) == fingerprint and not force:
        expires_at = _as_datetime(latest.get("expires_at"))
        if expires_at and expires_at > now:
            return {
                "status": "cached",
                "job_id": None,
                "fingerprint": fingerprint,
                "insight": latest,
            }
        refreshed = _touch_insight_expiry(repo=repo, insight=latest, cache_hours=cache_hours)
        return {
            "status": "reused",
            "job_id": None,
            "fingerprint": fingerprint,
            "insight": refreshed,
        }

    active = _find_active_job_for_fingerprint(
        repo=repo,
        workspace_id=workspace_id,
        user_id=resolved_user_id,
        fingerprint=fingerprint,
    )
    if active and not force:
        return {
            "status": "already_pending",
            "job_id": _safe_str(active.get("job_id")),
            "fingerprint": fingerprint,
            "insight": latest,
        }

    job_id = uuid4().hex
    payload = {
        "job_id": job_id,
        "task_type": WORKSPACE_INSIGHTS_TASK_TYPE,
        "workspace_id": workspace_id,
        "user_id": resolved_user_id,
        "trigger": _safe_str(trigger) or "manual_refresh",
        "reason": _safe_str(reason),
        "status": "pending",
        "fingerprint": fingerprint,
        "fingerprint_basis": fingerprint_basis,
        "retry_count": 0,
        "max_retries": 1,
        "input": {
            "top_k": max(3, int(top_k or DEFAULT_TOP_K)),
            "max_context_tokens": max(500, int(max_context_tokens or DEFAULT_MAX_CONTEXT_TOKENS)),
        },
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    _persist_job(repo=repo, payload=payload, merge=False)
    return {
        "status": "queued",
        "job_id": job_id,
        "fingerprint": fingerprint,
        "insight": latest,
    }


async def process_workspace_insights_job(
    *,
    repo: ResearchRepository,
    job_id: str,
    worker_id: str = "workspace_insights_worker",
) -> Optional[Dict[str, Any]]:
    target_job_id = _safe_str(job_id)
    if not target_job_id:
        return None
    claimed = _claim_job(repo=repo, job_id=target_job_id, worker_id=worker_id)
    if claimed is None:
        return get_workspace_insights_job(repo=repo, job_id=target_job_id)
    if _safe_str(claimed.get("status")).lower() != "running":
        return claimed

    workspace_id = _coerce_int(claimed.get("workspace_id"), 0)
    user_id = _coerce_int(claimed.get("user_id"), 0)
    if workspace_id <= 0 or user_id <= 0:
        return _fail_job(
            repo=repo,
            job_id=target_job_id,
            error_message="Invalid workspace insights job payload.",
        )

    try:
        fingerprint = _safe_str(claimed.get("fingerprint"))
        existing = get_latest_workspace_insights(
            repo=repo,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        if existing and _safe_str(existing.get("fingerprint")) == fingerprint:
            reused = _touch_insight_expiry(
                repo=repo,
                insight=existing,
                cache_hours=DEFAULT_CACHE_HOURS,
            )
            return _complete_job(
                repo=repo,
                job_id=target_job_id,
                result={
                    "insight_id": _safe_str(reused.get("insight_id")),
                    "from_cache": True,
                    "confidence": float(reused.get("confidence") or 0.0),
                    "retrieved_sources": len(reused.get("sources") or []),
                },
                processing_started_at=claimed.get("processing_started_at"),
            )

        input_blob = claimed.get("input") or {}
        context_rows = await asyncio.wait_for(
            _build_context_rows(
                repo=repo,
                workspace_id=workspace_id,
                top_k=max(3, _coerce_int(input_blob.get("top_k"), DEFAULT_TOP_K)),
                max_context_tokens=max(
                    500,
                    _coerce_int(input_blob.get("max_context_tokens"), DEFAULT_MAX_CONTEXT_TOKENS),
                ),
            ),
            timeout=max(10, MAX_PROCESSING_SECONDS),
        )
        parsed_payload = _run_workspace_insights_model(
            repo=repo,
            user_id=user_id,
            context_rows=context_rows,
        )
        normalized = normalize_workspace_insights_payload(
            parsed_payload=parsed_payload,
            max_source_index=len(context_rows),
            max_items_per_section=DEFAULT_MAX_ITEMS_PER_SECTION,
        )
        source_refs = _extract_source_refs_from_payload(normalized)
        sources_catalog = _build_sources_catalog(
            context_rows=context_rows,
            only_refs=source_refs if source_refs else None,
        )
        confidence = _calculate_confidence(
            normalized_payload=normalized,
            context_rows=context_rows,
        )
        now = _utcnow()
        insight_id = f"wsi_{workspace_id}_{user_id}_{_safe_str(claimed.get('fingerprint'))[:16]}"
        insight_doc = {
            "insight_id": insight_id,
            "task_type": WORKSPACE_INSIGHTS_TASK_TYPE,
            "workspace_id": workspace_id,
            "user_id": user_id,
            "fingerprint": _safe_str(claimed.get("fingerprint")),
            "job_id": target_job_id,
            "trigger": _safe_str(claimed.get("trigger")) or "manual_refresh",
            "disclaimer": WORKSPACE_INSIGHTS_DISCLAIMER,
            "payload": normalized,
            "sources": sources_catalog,
            "confidence": confidence,
            "context_count": len(context_rows),
            "source_ref_count": len(source_refs),
            "generated_at": now,
            "updated_at": now,
            "expires_at": now + timedelta(hours=DEFAULT_CACHE_HOURS),
        }
        _persist_insight(repo=repo, payload=insight_doc, merge=False)
        return _complete_job(
            repo=repo,
            job_id=target_job_id,
            result={
                "insight_id": insight_id,
                "from_cache": False,
                "confidence": confidence,
                "retrieved_sources": len(sources_catalog),
            },
            processing_started_at=claimed.get("processing_started_at"),
        )
    except Exception as exc:
        logger.exception("workspace_insights_job_failed job_id=%s", target_job_id)
        return _fail_job(
            repo=repo,
            job_id=target_job_id,
            error_message=str(exc) or "Workspace insights job failed.",
        )


async def get_or_generate_workspace_insights(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: int,
    refresh: bool = False,
    run_inline: bool = True,
    trigger: str = "dashboard_open",
) -> Dict[str, Any]:
    latest = get_latest_workspace_insights(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    enqueue_result = enqueue_workspace_insights_job(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
        trigger=trigger,
        force=refresh,
    )
    status = _safe_str(enqueue_result.get("status")) or "queued"
    job_id = _safe_str(enqueue_result.get("job_id"))
    if status in {"cached", "reused"}:
        insight = enqueue_result.get("insight") if isinstance(enqueue_result.get("insight"), dict) else latest
        return {
            "status": status,
            "job": None,
            "insight": insight,
        }

    job: Optional[Dict[str, Any]] = None
    if job_id and run_inline:
        job = await process_workspace_insights_job(
            repo=repo,
            job_id=job_id,
            worker_id="api_inline",
        )
        if job is None:
            job = get_workspace_insights_job(repo=repo, job_id=job_id)
        # Firestore visibility can lag immediately after enqueue; retry inline once.
        if _safe_str((job or {}).get("status")).lower() == "pending":
            retried = await process_workspace_insights_job(
                repo=repo,
                job_id=job_id,
                worker_id="api_inline_retry",
            )
            if retried is not None:
                job = retried
    elif job_id:
        job = get_workspace_insights_job(repo=repo, job_id=job_id)

    refreshed_latest = get_latest_workspace_insights(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    response_status = status
    job_status = _safe_str((job or {}).get("status")).lower()
    if job_status == "completed":
        response_status = "completed"
    elif job_status == "failed":
        response_status = "failed"
    elif job_status == "pending":
        response_status = "pending"
    elif status == "already_pending":
        response_status = "pending"
    return {
        "status": response_status,
        "job": job,
        "insight": refreshed_latest or latest,
    }


def queue_workspace_insights_job_best_effort(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: Optional[int] = None,
    trigger: str,
    reason: Optional[str] = None,
    force: bool = False,
) -> Optional[str]:
    try:
        queued = enqueue_workspace_insights_job(
            repo=repo,
            workspace_id=workspace_id,
            user_id=user_id,
            trigger=trigger,
            reason=reason,
            force=force,
        )
        return _safe_str(queued.get("job_id")) or None
    except Exception as exc:
        logger.debug(
            "Workspace insights enqueue skipped workspace_id=%s trigger=%s: %s",
            workspace_id,
            trigger,
            exc,
        )
        return None
