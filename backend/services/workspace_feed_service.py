from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import uuid4

from google.cloud.firestore_v1.base_query import FieldFilter

from repositories import ResearchRepository
from services.workspace_insights_service import (
    build_workspace_state_fingerprint,
    get_latest_workspace_insights,
    get_or_generate_workspace_insights,
)


logger = logging.getLogger(__name__)

WORKSPACE_FEED_TASK_TYPE = "workspace_feed"
WORKSPACE_FEED_DISCLAIMER = (
    "Feed items are AI-assisted signals from your workspace evidence. "
    "Always validate by opening linked source papers."
)
FEED_TYPES: Tuple[str, ...] = ("trend", "contradiction", "recommendation")
DEFAULT_CACHE_HOURS = max(1, int(os.getenv("WORKSPACE_FEED_CACHE_HOURS", "8") or 8))
DEFAULT_PAGE_SIZE = max(5, int(os.getenv("WORKSPACE_FEED_PAGE_SIZE", "15") or 15))
DEFAULT_MAX_ITEMS = max(6, int(os.getenv("WORKSPACE_FEED_MAX_ITEMS", "30") or 30))
PERIODIC_MAX_WORKSPACES = max(
    1, int(os.getenv("WORKSPACE_FEED_PERIODIC_MAX_WORKSPACES", "10") or 10)
)
MAX_PROCESSING_SECONDS = max(
    30,
    int(os.getenv("WORKSPACE_FEED_TIMEOUT_SECONDS", "180") or 180),
)
JOB_STUCK_TIMEOUT_SECONDS = max(
    MAX_PROCESSING_SECONDS,
    int(os.getenv("WORKSPACE_FEED_STUCK_TIMEOUT_SECONDS", str(MAX_PROCESSING_SECONDS)) or MAX_PROCESSING_SECONDS),
)

_IN_MEMORY_LOCK = Lock()
_IN_MEMORY_FEED: Dict[str, Dict[str, Any]] = {}
_IN_MEMORY_JOBS: Dict[str, Dict[str, Any]] = {}


def _log_job_event(event: str, **fields: Any) -> None:
    logger.info(json.dumps({"event": event, **fields}, default=str))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def _as_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return None
    return None


def _to_iso(value: Any) -> str:
    dt = _as_datetime(value) or _utcnow()
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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
            pass
    in_memory = getattr(repo, "_workspaces", None)
    if isinstance(in_memory, dict):
        workspace = in_memory.get(int(workspace_id))
        owner_id = _coerce_int(getattr(workspace, "user_id", 0), 0)
        return owner_id if owner_id > 0 else None
    return None


def _unique_ints(values: Sequence[Any], *, max_items: int = 6) -> List[int]:
    result: List[int] = []
    for value in values:
        item = _coerce_int(value, 0)
        if item <= 0 or item in result:
            continue
        result.append(item)
        if len(result) >= max(1, int(max_items)):
            break
    return result


def _parse_paper_id(source_id: str) -> Optional[int]:
    parts = _safe_str(source_id).replace("paper_", "paper:").split(":")
    if len(parts) < 2:
        return None
    item = _coerce_int(parts[-1], 0)
    return item if item > 0 else None


def _persist_feed_item(*, repo: ResearchRepository, payload: Dict[str, Any], merge: bool = False) -> None:
    feed_item_id = _safe_str(payload.get("feed_item_id"))
    if not feed_item_id:
        raise ValueError("feed_item_id is required")
    collection = _collection(repo, "workspace_feed")
    if collection is not None:
        collection.document(feed_item_id).set(payload, merge=bool(merge))
        return
    with _IN_MEMORY_LOCK:
        current = _IN_MEMORY_FEED.get(feed_item_id, {})
        if merge:
            merged = dict(current)
            merged.update(payload)
            _IN_MEMORY_FEED[feed_item_id] = merged
        else:
            _IN_MEMORY_FEED[feed_item_id] = dict(payload)


def _get_feed_item(*, repo: ResearchRepository, feed_item_id: str) -> Optional[Dict[str, Any]]:
    target = _safe_str(feed_item_id)
    if not target:
        return None
    collection = _collection(repo, "workspace_feed")
    if collection is not None:
        snapshot = collection.document(target).get()
        if not snapshot.exists:
            return None
        return snapshot.to_dict() or {}
    with _IN_MEMORY_LOCK:
        row = _IN_MEMORY_FEED.get(target)
        return dict(row) if row else None


def _list_feed_docs(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: int,
    include_archived: bool = False,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    collection = _collection(repo, "workspace_feed")
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
                snapshots = query.order_by("created_at", direction="DESCENDING").limit(250).stream()
            except Exception:
                snapshots = query.stream()
        except Exception:
            snapshots = []
        for snapshot in snapshots:
            payload = snapshot.to_dict() or {}
            if not include_archived and bool(payload.get("archived")):
                continue
            rows.append(payload)
    else:
        with _IN_MEMORY_LOCK:
            for payload in _IN_MEMORY_FEED.values():
                if _coerce_int(payload.get("workspace_id"), 0) != int(workspace_id):
                    continue
                if _coerce_int(payload.get("user_id"), 0) != int(user_id):
                    continue
                if not include_archived and bool(payload.get("archived")):
                    continue
                rows.append(dict(payload))
    rows.sort(
        key=lambda row: (
            float(row.get("importance_score") or 0.0),
            _as_datetime(row.get("created_at")) or _utcnow(),
        ),
        reverse=True,
    )
    return rows


def _persist_job(*, repo: ResearchRepository, payload: Dict[str, Any], merge: bool = False) -> None:
    job_id = _safe_str(payload.get("job_id"))
    if not job_id:
        raise ValueError("job_id is required")
    collection = _collection(repo, "workspace_feed_jobs")
    if collection is not None:
        collection.document(job_id).set(payload, merge=bool(merge))
        return
    with _IN_MEMORY_LOCK:
        current = _IN_MEMORY_JOBS.get(job_id, {})
        if merge:
            merged = dict(current)
            merged.update(payload)
            _IN_MEMORY_JOBS[job_id] = merged
        else:
            _IN_MEMORY_JOBS[job_id] = dict(payload)


def get_workspace_feed_job(*, repo: ResearchRepository, job_id: str) -> Optional[Dict[str, Any]]:
    target = _safe_str(job_id)
    if not target:
        return None
    collection = _collection(repo, "workspace_feed_jobs")
    if collection is not None:
        snapshot = collection.document(target).get()
        if not snapshot.exists:
            return None
        return snapshot.to_dict() or {}
    with _IN_MEMORY_LOCK:
        row = _IN_MEMORY_JOBS.get(target)
        return dict(row) if row else None


def _list_jobs(
    *,
    repo: ResearchRepository,
    statuses: Optional[Sequence[str]] = None,
    workspace_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    status_set = {str(item).lower() for item in (statuses or [])}
    rows: List[Dict[str, Any]] = []
    collection = _collection(repo, "workspace_feed_jobs")
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
        if len(status_set) == 1:
            query = query.where(
                filter=FieldFilter("status", "==", next(iter(status_set)))
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
            rows.append(payload)
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
                rows.append(dict(payload))
    rows.sort(key=lambda row: _as_datetime(row.get("created_at")) or _utcnow())
    return rows


def list_pending_workspace_feed_jobs(*, repo: ResearchRepository, limit: int = 20) -> List[Dict[str, Any]]:
    rows = _list_jobs(repo=repo, statuses=("pending",))
    return rows[: max(1, int(limit))]


def list_stuck_workspace_feed_jobs(
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


def recover_stuck_workspace_feed_jobs(
    *,
    repo: ResearchRepository,
    timeout_seconds: int = JOB_STUCK_TIMEOUT_SECONDS,
    limit: int = 50,
) -> int:
    recovered = 0
    for row in list_stuck_workspace_feed_jobs(
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
            "workspace_feed_stuck_jobs_recovered",
            recovered=recovered,
            timeout_seconds=int(timeout_seconds),
        )
    return recovered


def _claim_job(
    *,
    repo: ResearchRepository,
    job_id: str,
    worker_id: str,
) -> Optional[Dict[str, Any]]:
    current = get_workspace_feed_job(repo=repo, job_id=job_id)
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
                "workspace_feed_job_recovered",
                job_id=_safe_str(job_id),
                stale_seconds=round((now - started).total_seconds(), 3),
            )
            current = get_workspace_feed_job(repo=repo, job_id=job_id) or current
            current_status = _safe_str(current.get("status")).lower()
    if current_status != "pending":
        return None
    _persist_job(
        repo=repo,
        payload={
            "job_id": _safe_str(job_id),
            "status": "running",
            "claimed_by": _safe_str(worker_id),
            "claimed_at": now,
            "processing_started_at": current.get("processing_started_at") or now,
            "updated_at": now,
        },
        merge=True,
    )
    _log_job_event(
        "workspace_feed_job_transition",
        job_id=_safe_str(job_id),
        status="running",
        worker_id=_safe_str(worker_id),
    )
    return get_workspace_feed_job(repo=repo, job_id=job_id)


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
    _persist_job(
        repo=repo,
        payload={
            "job_id": _safe_str(job_id),
            "status": "completed",
            "result": dict(result or {}),
            "error": None,
            "processing_completed_at": now,
            "latency_ms": latency_ms,
            "updated_at": now,
        },
        merge=True,
    )
    _log_job_event(
        "workspace_feed_job_transition",
        job_id=_safe_str(job_id),
        status="completed",
        latency_ms=latency_ms,
    )
    return get_workspace_feed_job(repo=repo, job_id=job_id)


def _fail_job(
    *,
    repo: ResearchRepository,
    job_id: str,
    error_message: str,
) -> Optional[Dict[str, Any]]:
    current = get_workspace_feed_job(repo=repo, job_id=job_id) or {}
    now = _utcnow()
    retry_count = _coerce_int(current.get("retry_count"), 0)
    max_retries = max(0, _coerce_int(current.get("max_retries"), 1))
    next_retry_count = retry_count + 1
    should_retry = next_retry_count <= max_retries
    started = _as_datetime(current.get("processing_started_at"))
    latency_ms = max(0, int((now - started).total_seconds() * 1000)) if started else None

    updates: Dict[str, Any] = {
        "job_id": _safe_str(job_id),
        "error": _safe_str(error_message)[:1200] or "Workspace feed job failed.",
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
        "workspace_feed_job_transition",
        job_id=_safe_str(job_id),
        status=_safe_str(updates.get("status")),
        retry_count=next_retry_count,
        max_retries=max_retries,
        latency_ms=latency_ms,
    )
    return get_workspace_feed_job(repo=repo, job_id=job_id)


def build_workspace_feed_fingerprint(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: int,
) -> Tuple[str, Dict[str, Any]]:
    digest, basis = build_workspace_state_fingerprint(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    feed_basis = {
        "workspace_digest": digest,
        "workspace_id": int(workspace_id),
        "user_id": int(user_id),
        "paper_count": len(basis.get("papers") or []),
        "report_count": len(basis.get("reports") or []),
        "comparison_count": len(basis.get("comparisons") or []),
        "checker_count": len(basis.get("checker_jobs") or []),
    }
    payload = json.dumps(feed_basis, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest(), feed_basis


def _importance_for_type(feed_type: str) -> float:
    if feed_type == "contradiction":
        return 0.9
    if feed_type == "trend":
        return 0.74
    return 0.66


def _item_signature(item: Dict[str, Any]) -> str:
    raw = f"{_safe_str(item.get('type')).lower()}|{_safe_str(item.get('title')).lower()}|{_safe_str(item.get('description')).lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _build_feed_items_from_insight(
    *,
    insight: Optional[Dict[str, Any]],
    workspace_id: int,
    user_id: int,
    max_items: int,
) -> List[Dict[str, Any]]:
    insight_payload = insight.get("payload") if isinstance(insight, dict) and isinstance(insight.get("payload"), dict) else {}
    sources = insight.get("sources") if isinstance(insight, dict) and isinstance(insight.get("sources"), list) else []
    source_map = {int(_coerce_int(row.get("source_index"), 0)): row for row in sources if _coerce_int(row.get("source_index"), 0) > 0}
    rows: List[Dict[str, Any]] = []
    section_map = [
        ("key_themes", "trend", "Key theme"),
        ("emerging_trends", "trend", "Emerging trend"),
        ("contradictions", "contradiction", "Contradiction detected"),
        ("important_findings", "trend", "Important finding"),
        ("research_gaps", "recommendation", "Research gap identified"),
        ("recommended_next_steps", "recommendation", "Recommended next step"),
    ]
    now = _utcnow()
    for section_key, feed_type, label in section_map:
        section_rows = insight_payload.get(section_key)
        if not isinstance(section_rows, list):
            continue
        for entry in section_rows:
            if not isinstance(entry, dict):
                continue
            text = _safe_str(entry.get("text"))
            if not text:
                continue
            refs = _unique_ints(entry.get("source_refs") or [], max_items=6)
            item_sources = [source_map.get(ref) for ref in refs if ref in source_map]
            item_sources = [row for row in item_sources if isinstance(row, dict)]
            related_papers = _unique_ints(
                [_parse_paper_id(_safe_str(row.get("source_id"))) for row in item_sources], max_items=4
            )
            title = f"{label}: {text[:72]}{'...' if len(text) > 72 else ''}"
            rows.append(
                {
                    "feed_item_id": f"wsf_{workspace_id}_{user_id}_{uuid4().hex[:14]}",
                    "task_type": WORKSPACE_FEED_TASK_TYPE,
                    "workspace_id": int(workspace_id),
                    "user_id": int(user_id),
                    "type": feed_type,
                    "title": title,
                    "description": text[:900],
                    "related_papers": related_papers,
                    "importance_score": _importance_for_type(feed_type),
                    "source_refs": refs,
                    "sources": item_sources[:4],
                    "read": False,
                    "read_at": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            if len(rows) >= max(1, int(max_items)):
                return rows
    return rows


def _append_recent_paper_recommendation(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: int,
    rows: List[Dict[str, Any]],
) -> None:
    papers = repo.list_papers_for_workspace(int(workspace_id))
    papers.sort(key=lambda paper: int(getattr(paper, "id", 0) or 0), reverse=True)
    if not papers:
        return
    latest = papers[0]
    now = _utcnow()
    rows.append(
        {
            "feed_item_id": f"wsf_{workspace_id}_{user_id}_{uuid4().hex[:14]}",
            "task_type": WORKSPACE_FEED_TASK_TYPE,
            "workspace_id": int(workspace_id),
            "user_id": int(user_id),
            "type": "recommendation",
            "title": f"New paper added: {_safe_str(getattr(latest, 'title', 'Untitled'))[:80]}",
            "description": "Review this paper and connect it to current workspace themes and contradictions.",
            "related_papers": [int(getattr(latest, "id", 0) or 0)],
            "importance_score": 0.7,
            "source_refs": [],
            "sources": [],
            "read": False,
            "read_at": None,
            "created_at": now,
            "updated_at": now,
        }
    )


def _store_feed_items_incremental(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: int,
    fingerprint: str,
    trigger: str,
    job_id: str,
    rows: Sequence[Dict[str, Any]],
) -> int:
    now = _utcnow()
    existing = _list_feed_docs(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
        include_archived=True,
    )
    existing_by_signature = {_item_signature(row): row for row in existing}
    active_ids: List[str] = []
    for row in rows:
        signature = _item_signature(row)
        prior = existing_by_signature.get(signature, {})
        feed_item_id = _safe_str(prior.get("feed_item_id")) or _safe_str(row.get("feed_item_id"))
        payload = dict(row)
        payload.update(
            {
                "feed_item_id": feed_item_id,
                "fingerprint": _safe_str(fingerprint),
                "job_id": _safe_str(job_id),
                "trigger": _safe_str(trigger) or "dashboard_open",
                "archived": False,
                "updated_at": now,
                "generated_at": now,
                "expires_at": now + timedelta(hours=DEFAULT_CACHE_HOURS),
                "created_at": prior.get("created_at") or row.get("created_at") or now,
                "read": bool(prior.get("read")),
                "read_at": prior.get("read_at"),
            }
        )
        _persist_feed_item(repo=repo, payload=payload, merge=bool(prior))
        active_ids.append(feed_item_id)

    active_set = set(active_ids)
    for row in existing:
        feed_item_id = _safe_str(row.get("feed_item_id"))
        if not feed_item_id or feed_item_id in active_set or bool(row.get("archived")):
            continue
        _persist_feed_item(
            repo=repo,
            payload={"feed_item_id": feed_item_id, "archived": True, "updated_at": now},
            merge=True,
        )
    return len(active_ids)


def enqueue_workspace_feed_job(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: Optional[int] = None,
    trigger: str = "dashboard_open",
    force: bool = False,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    workspace_id = int(workspace_id)
    resolved_user_id = int(user_id or 0)
    if resolved_user_id <= 0:
        resolved_user_id = int(_resolve_workspace_owner_user_id(repo=repo, workspace_id=workspace_id) or 0)
    if workspace_id <= 0 or resolved_user_id <= 0:
        raise ValueError("workspace_id and user_id are required for workspace feed.")

    now = _utcnow()
    fingerprint, _ = build_workspace_feed_fingerprint(
        repo=repo,
        workspace_id=workspace_id,
        user_id=resolved_user_id,
    )
    latest = _list_feed_docs(repo=repo, workspace_id=workspace_id, user_id=resolved_user_id, include_archived=False)
    if latest and not force:
        latest_item = latest[0]
        expires_at = _as_datetime(latest_item.get("expires_at"))
        if _safe_str(latest_item.get("fingerprint")) == fingerprint and expires_at and expires_at > now:
            return {"status": "cached", "job_id": None, "fingerprint": fingerprint}

    pending = [
        row
        for row in _list_jobs(
            repo=repo,
            statuses=("pending", "running"),
            workspace_id=workspace_id,
            user_id=resolved_user_id,
        )
        if _safe_str(row.get("fingerprint")) == fingerprint
    ]
    if pending and not force:
        return {"status": "already_pending", "job_id": _safe_str(pending[0].get("job_id")), "fingerprint": fingerprint}

    job_id = uuid4().hex
    _persist_job(
        repo=repo,
        payload={
            "job_id": job_id,
            "task_type": WORKSPACE_FEED_TASK_TYPE,
            "workspace_id": workspace_id,
            "user_id": resolved_user_id,
            "status": "pending",
            "trigger": _safe_str(trigger) or "dashboard_open",
            "reason": _safe_str(reason),
            "fingerprint": fingerprint,
            "retry_count": 0,
            "max_retries": 1,
            "claimed_by": None,
            "claimed_at": None,
            "created_at": now,
            "updated_at": now,
            "result": None,
            "error": None,
        },
        merge=False,
    )
    return {"status": "queued", "job_id": job_id, "fingerprint": fingerprint}


async def process_workspace_feed_job(
    *,
    repo: ResearchRepository,
    job_id: str,
    worker_id: str = "workspace_feed_worker",
) -> Optional[Dict[str, Any]]:
    target_job_id = _safe_str(job_id)
    if not target_job_id:
        return None
    claimed = _claim_job(repo=repo, job_id=target_job_id, worker_id=worker_id)
    if claimed is None:
        return get_workspace_feed_job(repo=repo, job_id=target_job_id)
    if _safe_str(claimed.get("status")).lower() != "running":
        return claimed

    workspace_id = _coerce_int(claimed.get("workspace_id"), 0)
    user_id = _coerce_int(claimed.get("user_id"), 0)
    if workspace_id <= 0 or user_id <= 0:
        return _fail_job(
            repo=repo,
            job_id=target_job_id,
            error_message="Invalid workspace feed job.",
        )

    try:
        await get_or_generate_workspace_insights(
            repo=repo,
            workspace_id=workspace_id,
            user_id=user_id,
            refresh=False,
            run_inline=True,
            trigger="workspace_feed_job",
        )
        insight = get_latest_workspace_insights(
            repo=repo,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        feed_rows = _build_feed_items_from_insight(
            insight=insight,
            workspace_id=workspace_id,
            user_id=user_id,
            max_items=DEFAULT_MAX_ITEMS,
        )
        if len(feed_rows) < 4:
            _append_recent_paper_recommendation(
                repo=repo,
                workspace_id=workspace_id,
                user_id=user_id,
                rows=feed_rows,
            )
        fingerprint = _safe_str(claimed.get("fingerprint"))
        item_count = _store_feed_items_incremental(
            repo=repo,
            workspace_id=workspace_id,
            user_id=user_id,
            fingerprint=fingerprint,
            trigger=_safe_str(claimed.get("trigger")),
            job_id=target_job_id,
            rows=feed_rows,
        )
        return _complete_job(
            repo=repo,
            job_id=target_job_id,
            result={"item_count": item_count},
            processing_started_at=claimed.get("processing_started_at"),
        )
    except Exception as exc:
        logger.exception("workspace_feed_job_failed job_id=%s", target_job_id)
        return _fail_job(
            repo=repo,
            job_id=target_job_id,
            error_message=_safe_str(exc)[:1200] or "Workspace feed job failed.",
        )


async def get_or_generate_workspace_feed(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: int,
    refresh: bool = False,
    run_inline: bool = True,
    trigger: str = "dashboard_open",
) -> Dict[str, Any]:
    queued = enqueue_workspace_feed_job(
        repo=repo,
        workspace_id=workspace_id,
        user_id=user_id,
        trigger=trigger,
        force=refresh,
    )
    status = _safe_str(queued.get("status")) or "queued"
    job_id = _safe_str(queued.get("job_id"))
    job = None
    if job_id and run_inline:
        job = await process_workspace_feed_job(repo=repo, job_id=job_id, worker_id="api_inline")
        if job is None:
            job = get_workspace_feed_job(repo=repo, job_id=job_id)
        # Firestore visibility can lag immediately after enqueue; retry inline once.
        if _safe_str((job or {}).get("status")).lower() == "pending":
            retried = await process_workspace_feed_job(
                repo=repo,
                job_id=job_id,
                worker_id="api_inline_retry",
            )
            if retried is not None:
                job = retried
    elif job_id:
        job = get_workspace_feed_job(repo=repo, job_id=job_id)

    resolved_status = status if not job else _safe_str(job.get("status")) or status
    if _safe_str(resolved_status).lower() == "already_pending":
        resolved_status = "pending"
    return {"status": resolved_status, "job": job}


def get_workspace_feed_page(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: int,
    sort: str = "importance",
    limit: int = DEFAULT_PAGE_SIZE,
    cursor: Optional[str] = None,
    include_read: bool = True,
) -> Dict[str, Any]:
    all_rows = _list_feed_docs(repo=repo, workspace_id=workspace_id, user_id=user_id, include_archived=False)
    unread_count = sum(1 for row in all_rows if not bool(row.get("read")))
    rows = list(all_rows)
    if not include_read:
        rows = [row for row in rows if not bool(row.get("read"))]
    if _safe_str(sort).lower() == "recent":
        rows.sort(
            key=lambda row: (_as_datetime(row.get("created_at")) or _utcnow(), float(row.get("importance_score") or 0.0)),
            reverse=True,
        )
    else:
        rows.sort(
            key=lambda row: (float(row.get("importance_score") or 0.0), _as_datetime(row.get("created_at")) or _utcnow()),
            reverse=True,
        )
    offset = max(0, _coerce_int(cursor, 0))
    page_size = max(1, min(50, int(limit)))
    page = rows[offset : offset + page_size]
    next_cursor = str(offset + len(page)) if offset + len(page) < len(rows) else None
    return {"items": page, "next_cursor": next_cursor, "total_count": len(rows), "unread_count": unread_count}


def mark_workspace_feed_item_read(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: int,
    feed_item_id: str,
    read: bool = True,
) -> Optional[Dict[str, Any]]:
    row = _get_feed_item(repo=repo, feed_item_id=feed_item_id)
    if not row:
        return None
    if _coerce_int(row.get("workspace_id"), 0) != int(workspace_id):
        return None
    if _coerce_int(row.get("user_id"), 0) != int(user_id):
        return None
    _persist_feed_item(
        repo=repo,
        payload={
            "feed_item_id": _safe_str(feed_item_id),
            "read": bool(read),
            "read_at": _utcnow() if read else None,
            "updated_at": _utcnow(),
        },
        merge=True,
    )
    return _get_feed_item(repo=repo, feed_item_id=feed_item_id)


def queue_workspace_feed_job_best_effort(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: Optional[int] = None,
    trigger: str,
    reason: Optional[str] = None,
    force: bool = False,
) -> Optional[str]:
    try:
        queued = enqueue_workspace_feed_job(
            repo=repo,
            workspace_id=workspace_id,
            user_id=user_id,
            trigger=trigger,
            force=force,
            reason=reason,
        )
        return _safe_str(queued.get("job_id")) or None
    except Exception as exc:
        logger.debug("workspace feed enqueue skipped workspace_id=%s trigger=%s: %s", workspace_id, trigger, exc)
        return None


def enqueue_periodic_workspace_feed_jobs(
    *,
    repo: ResearchRepository,
    max_workspaces: int = PERIODIC_MAX_WORKSPACES,
) -> int:
    count = 0
    workspaces: List[Dict[str, Any]] = []
    db = getattr(repo, "db", None)
    if db is not None:
        for snapshot in db.collection("workspaces").stream():
            payload = snapshot.to_dict() or {}
            payload.setdefault("id", _coerce_int(snapshot.id, 0))
            workspaces.append(payload)
    else:
        in_memory = getattr(repo, "_workspaces", None)
        if isinstance(in_memory, dict):
            workspaces = [dict(vars(ws)) for ws in in_memory.values()]
    now = _utcnow()
    for workspace in workspaces:
        workspace_id = _coerce_int(workspace.get("id"), 0)
        user_id = _coerce_int(workspace.get("user_id"), 0)
        if workspace_id <= 0 or user_id <= 0:
            continue
        latest = _list_feed_docs(repo=repo, workspace_id=workspace_id, user_id=user_id, include_archived=False)
        latest_item = latest[0] if latest else None
        expires_at = _as_datetime(latest_item.get("expires_at")) if latest_item else None
        if expires_at and expires_at > now:
            continue
        queued = enqueue_workspace_feed_job(
            repo=repo,
            workspace_id=workspace_id,
            user_id=user_id,
            trigger="periodic_refresh",
            force=False,
        )
        if _safe_str(queued.get("status")) in {"queued", "already_pending"}:
            count += 1
        if count >= max(1, int(max_workspaces)):
            break
    return count


def reset_workspace_feed_memory_state() -> None:
    with _IN_MEMORY_LOCK:
        _IN_MEMORY_FEED.clear()
        _IN_MEMORY_JOBS.clear()
