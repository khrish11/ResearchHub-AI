from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Sequence, Tuple

from google.cloud.firestore_v1.base_query import FieldFilter

from repositories import ResearchRepository
from repositories.research import Paper, User, Workspace
from services.workspace_feed_service import (
    WORKSPACE_FEED_DISCLAIMER,
    build_workspace_feed_fingerprint,
)
from services.workspace_insights_service import WORKSPACE_INSIGHTS_DISCLAIMER


logger = logging.getLogger(__name__)

ONBOARDING_STEP_UPLOAD = "upload_paper"
ONBOARDING_STEP_EXPLAIN = "explain_paper"
ONBOARDING_STEP_COMPARE = "compare_papers"
ONBOARDING_STEP_REPORT = "generate_report"
ONBOARDING_STEP_ORDER: Tuple[str, ...] = (
    ONBOARDING_STEP_UPLOAD,
    ONBOARDING_STEP_EXPLAIN,
    ONBOARDING_STEP_COMPARE,
    ONBOARDING_STEP_REPORT,
)

ONBOARDING_STEPS: Dict[str, Dict[str, str]] = {
    ONBOARDING_STEP_UPLOAD: {
        "title": "Upload a paper",
        "description": "Import your first paper into this workspace.",
        "action_label": "Upload Paper",
        "action_path": "/upload",
    },
    ONBOARDING_STEP_EXPLAIN: {
        "title": "Try Explain This Paper",
        "description": "Open a paper and generate the instant AI explanation overlay.",
        "action_label": "Explain Paper",
        "action_path": "/workspace/{workspace_id}",
    },
    ONBOARDING_STEP_COMPARE: {
        "title": "Compare two papers",
        "description": "Run a paper-vs-paper comparison to surface differences and contradictions.",
        "action_label": "Compare Papers",
        "action_path": "/compare",
    },
    ONBOARDING_STEP_REPORT: {
        "title": "Generate a report",
        "description": "Create your first synthesized research report from workspace evidence.",
        "action_label": "Generate Report",
        "action_path": "/research-report",
    },
}

COPILOT_SUGGESTED_PROMPTS: Tuple[str, ...] = (
    "Summarize this paper",
    "Compare these papers",
    "What are the main trends?",
)

DEMO_PAPERS: Tuple[Dict[str, str], ...] = (
    {
        "title": "Efficient Retrieval-Augmented Generation for Clinical QA",
        "authors": "N. Patel, R. Kumar, E. Sun",
        "abstract": (
            "This paper evaluates retrieval-augmented generation for clinical question answering "
            "and reports consistent gains in factual precision on hospital discharge datasets."
        ),
        "url": "https://doi.org/10.5555/soyog.demo.001",
        "doi": "10.5555/soyog.demo.001",
        "source": "demo_seed",
    },
    {
        "title": "Distribution Shift Breaks Medical RAG Reliability",
        "authors": "J. Miller, A. Gomez",
        "abstract": (
            "The study finds that domain shift between institutions can reduce answer reliability "
            "for RAG systems and introduces contradiction analysis across cohorts."
        ),
        "url": "https://doi.org/10.5555/soyog.demo.002",
        "doi": "10.5555/soyog.demo.002",
        "source": "demo_seed",
    },
    {
        "title": "Lightweight Evidence Re-Ranking for Safer Scientific Assistants",
        "authors": "S. Iyer, M. Chen",
        "abstract": (
            "A compact reranker improves citation faithfulness and lowers unsupported claims "
            "without major latency penalties in constrained research workflows."
        ),
        "url": "https://doi.org/10.5555/soyog.demo.003",
        "doi": "10.5555/soyog.demo.003",
        "source": "demo_seed",
    },
)

DEMO_FEED_PREVIEW: Tuple[Dict[str, Any], ...] = (
    {
        "type": "contradiction",
        "title": "New contradiction found between baseline and shifted datasets",
        "description": "One paper reports strong gains while another reports regressions under shift.",
        "importance_score": 0.92,
    },
    {
        "type": "trend",
        "title": "Emerging trend: evidence re-ranking appears across recent papers",
        "description": "Multiple papers point to reranking as a key driver of grounded answer quality.",
        "importance_score": 0.82,
    },
    {
        "type": "recommendation",
        "title": "Suggested next action: compare reliability assumptions side-by-side",
        "description": "Run Compare Papers to inspect disagreement in evaluation settings and claims.",
        "importance_score": 0.78,
    },
)

_IN_MEMORY_LOCK = Lock()
_IN_MEMORY_ONBOARDING: Dict[str, Dict[str, Any]] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def _to_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    text = _safe_str(value)
    return text or None


def _collection(repo: ResearchRepository, name: str):  # type: ignore[no-untyped-def]
    db = getattr(repo, "db", None)
    if db is None:
        return None
    try:
        return db.collection(name)
    except Exception:
        return None


def _record_id(user_id: int, workspace_id: int) -> str:
    return f"onboard_{int(user_id)}_{int(workspace_id)}"


def _read_state(
    *,
    repo: ResearchRepository,
    user_id: int,
    workspace_id: int,
) -> Dict[str, Any]:
    row_id = _record_id(user_id, workspace_id)
    collection = _collection(repo, "workspace_onboarding")
    if collection is not None:
        snapshot = collection.document(row_id).get()
        if snapshot.exists:
            return snapshot.to_dict() or {}
        return {}
    with _IN_MEMORY_LOCK:
        row = _IN_MEMORY_ONBOARDING.get(row_id)
        return dict(row) if row else {}


def _persist_state(
    *,
    repo: ResearchRepository,
    user_id: int,
    workspace_id: int,
    payload: Dict[str, Any],
    merge: bool = True,
) -> Dict[str, Any]:
    row_id = _record_id(user_id, workspace_id)
    record = dict(payload)
    record.update(
        {
            "record_id": row_id,
            "user_id": int(user_id),
            "workspace_id": int(workspace_id),
            "updated_at": _utcnow(),
        }
    )
    collection = _collection(repo, "workspace_onboarding")
    if collection is not None:
        collection.document(row_id).set(record, merge=bool(merge))
        snapshot = collection.document(row_id).get()
        return snapshot.to_dict() or record
    with _IN_MEMORY_LOCK:
        current = _IN_MEMORY_ONBOARDING.get(row_id, {})
        if merge:
            merged = dict(current)
            merged.update(record)
            _IN_MEMORY_ONBOARDING[row_id] = merged
        else:
            _IN_MEMORY_ONBOARDING[row_id] = record
        return dict(_IN_MEMORY_ONBOARDING[row_id])


def _resolve_workspace(
    *,
    repo: ResearchRepository,
    user_id: int,
    workspace_id: Optional[int] = None,
    create_default: bool = True,
) -> Workspace:
    target = _coerce_int(workspace_id, 0)
    if target > 0:
        workspace = repo.find_workspace_for_user(int(target), int(user_id))
        if workspace is None:
            raise ValueError("Workspace not found or inaccessible.")
        return workspace
    rows = repo.list_workspaces_for_user(int(user_id))
    if rows:
        return rows[0]
    if not create_default:
        raise ValueError("Workspace is required.")
    return repo.get_or_create_default_workspace(int(user_id))


def _paper_count_for_workspace(
    *,
    repo: ResearchRepository,
    workspace_id: int,
) -> int:
    try:
        return len(repo.list_papers_for_workspace(int(workspace_id)))
    except Exception:
        return 0


def _load_completed_steps(raw: Sequence[Any]) -> List[str]:
    completed: List[str] = []
    for value in raw:
        step_id = _safe_str(value)
        if step_id in ONBOARDING_STEP_ORDER and step_id not in completed:
            completed.append(step_id)
    return completed


def _upsert_user_flag(
    *,
    repo: ResearchRepository,
    user: User,
    has_completed: bool,
) -> None:
    if bool(getattr(user, "has_completed_onboarding", False)) == bool(has_completed):
        return
    user.has_completed_onboarding = bool(has_completed)
    repo.save(user)
    _invalidate_user_cache(_safe_str(getattr(user, "email", "")))


def _invalidate_user_cache(email: str) -> None:
    target = _safe_str(email).lower()
    if not target:
        return
    try:
        from utils.user_cache import invalidate_user_cache

        invalidate_user_cache(target)
    except Exception:
        return


def _step_rows(
    *,
    workspace_id: int,
    completed: Sequence[str],
) -> List[Dict[str, Any]]:
    completed_set = set(completed)
    rows: List[Dict[str, Any]] = []
    for step_id in ONBOARDING_STEP_ORDER:
        meta = ONBOARDING_STEPS[step_id]
        action_path = _safe_str(meta.get("action_path")).format(workspace_id=workspace_id)
        rows.append(
            {
                "id": step_id,
                "title": _safe_str(meta.get("title")),
                "description": _safe_str(meta.get("description")),
                "action_label": _safe_str(meta.get("action_label")),
                "action_path": action_path,
                "completed": step_id in completed_set,
            }
        )
    return rows


def _ensure_completion_state(
    *,
    repo: ResearchRepository,
    user: User,
    workspace_id: int,
    completed_steps: Sequence[str],
) -> None:
    all_complete = len(set(completed_steps).intersection(set(ONBOARDING_STEP_ORDER))) == len(
        ONBOARDING_STEP_ORDER
    )
    if all_complete:
        _upsert_user_flag(repo=repo, user=user, has_completed=True)
        _persist_state(
            repo=repo,
            user_id=int(user.id or 0),
            workspace_id=int(workspace_id),
            payload={"completed_at": _utcnow()},
            merge=True,
        )


def _build_status_payload(
    *,
    repo: ResearchRepository,
    user: User,
    workspace: Workspace,
    state: Dict[str, Any],
) -> Dict[str, Any]:
    paper_count = _paper_count_for_workspace(repo=repo, workspace_id=int(workspace.id))
    completed_steps = _load_completed_steps(state.get("completed_steps") or [])
    if paper_count > 0 and ONBOARDING_STEP_UPLOAD not in completed_steps:
        completed_steps.append(ONBOARDING_STEP_UPLOAD)
    completed_steps = [step for step in ONBOARDING_STEP_ORDER if step in completed_steps]
    progress = _clamp(len(completed_steps) / float(len(ONBOARDING_STEP_ORDER)))
    dismissed = bool(state.get("dismissed")) or bool(
        (getattr(user, "feature_flags", {}) or {}).get("onboarding_dismissed")
    )
    has_completed = bool(getattr(user, "has_completed_onboarding", False)) or progress >= 1.0
    if has_completed and not bool(getattr(user, "has_completed_onboarding", False)):
        _upsert_user_flag(repo=repo, user=user, has_completed=True)
    step_rows = _step_rows(workspace_id=int(workspace.id), completed=completed_steps)
    needs_onboarding = paper_count == 0 and not has_completed and not dismissed
    return {
        "workspace_id": int(workspace.id),
        "workspace_name": _safe_str(workspace.name),
        "paper_count": int(paper_count),
        "has_completed_onboarding": bool(has_completed),
        "dismissed": bool(dismissed),
        "needs_onboarding": bool(needs_onboarding),
        "progress": round(float(progress), 4),
        "completed_steps": completed_steps,
        "steps": step_rows,
        "copilot_prompts": list(COPILOT_SUGGESTED_PROMPTS),
        "demo": {
            "available": True,
            "seeded": bool(state.get("demo_seeded")),
            "seeded_at": _to_iso(state.get("demo_seeded_at")),
            "paper_ids": [
                int(value)
                for value in (state.get("demo_paper_ids") or [])
                if _coerce_int(value, 0) > 0
            ],
            "sample_papers": [
                {
                    "title": _safe_str(row.get("title")),
                    "authors": _safe_str(row.get("authors")),
                }
                for row in DEMO_PAPERS
            ],
            "sample_comparison": {
                "title": "Sample contradiction comparison",
                "description": "Preloaded comparison shows where claims diverge by dataset assumptions.",
            },
            "sample_report": {
                "title": "Sample workspace report",
                "description": "Preloaded report demonstrates structure, evidence narrative, and next actions.",
            },
            "sample_feed_items": list(DEMO_FEED_PREVIEW),
        },
    }


def get_onboarding_status(
    *,
    repo: ResearchRepository,
    user: User,
    workspace_id: Optional[int] = None,
) -> Dict[str, Any]:
    workspace = _resolve_workspace(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=workspace_id,
        create_default=True,
    )
    state = _read_state(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=int(workspace.id),
    )
    return _build_status_payload(
        repo=repo,
        user=user,
        workspace=workspace,
        state=state,
    )


def set_onboarding_dismissed(
    *,
    repo: ResearchRepository,
    user: User,
    workspace_id: Optional[int] = None,
    dismissed: bool = True,
) -> Dict[str, Any]:
    workspace = _resolve_workspace(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=workspace_id,
        create_default=True,
    )
    now = _utcnow()
    _persist_state(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=int(workspace.id),
        payload={
            "dismissed": bool(dismissed),
            "dismissed_at": now if dismissed else None,
            "created_at": now,
        },
        merge=True,
    )
    flags = dict(getattr(user, "feature_flags", {}) or {})
    flags["onboarding_dismissed"] = bool(dismissed)
    user.feature_flags = flags
    repo.save(user)
    _invalidate_user_cache(_safe_str(getattr(user, "email", "")))
    return get_onboarding_status(
        repo=repo,
        user=user,
        workspace_id=int(workspace.id),
    )


def record_onboarding_step(
    *,
    repo: ResearchRepository,
    user: User,
    workspace_id: int,
    step_id: str,
) -> Dict[str, Any]:
    clean_step = _safe_str(step_id)
    if clean_step not in ONBOARDING_STEP_ORDER:
        raise ValueError("Unsupported onboarding step.")
    workspace = _resolve_workspace(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=workspace_id,
        create_default=False,
    )
    state = _read_state(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=int(workspace.id),
    )
    completed_steps = _load_completed_steps(state.get("completed_steps") or [])
    if clean_step not in completed_steps:
        completed_steps.append(clean_step)
    now = _utcnow()
    _persist_state(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=int(workspace.id),
        payload={
            "completed_steps": completed_steps,
            "step_timestamps": {
                **(state.get("step_timestamps") or {}),
                clean_step: now,
            },
            "created_at": state.get("created_at") or now,
        },
        merge=True,
    )
    status = get_onboarding_status(
        repo=repo,
        user=user,
        workspace_id=int(workspace.id),
    )
    _ensure_completion_state(
        repo=repo,
        user=user,
        workspace_id=int(workspace.id),
        completed_steps=status.get("completed_steps") or [],
    )
    return status


def _find_demo_paper(
    *,
    papers: Sequence[Paper],
    target_title: str,
    target_doi: str,
) -> Optional[Paper]:
    title_norm = _safe_str(target_title).lower()
    doi_norm = _safe_str(target_doi).lower()
    for paper in papers:
        if _safe_str(getattr(paper, "doi", "")).lower() == doi_norm and doi_norm:
            return paper
    for paper in papers:
        if _safe_str(getattr(paper, "title", "")).lower() == title_norm:
            return paper
    return None


def _seed_demo_comparison(
    *,
    repo: ResearchRepository,
    user_id: int,
    paper_ids: Sequence[int],
    workspace_id: int,
) -> str:
    fingerprint = f"demo:onboarding:compare:{int(workspace_id)}"
    existing_id = ""
    if hasattr(repo, "find_paper_comparison_by_fingerprint"):
        try:
            existing = repo.find_paper_comparison_by_fingerprint(fingerprint)
            if existing:
                return str(existing.id)
        except Exception:
            pass
    collection = _collection(repo, "paper_comparisons")
    if collection is not None:
        for snapshot in collection.where(
            filter=FieldFilter("fingerprint", "==", fingerprint)
        ).limit(1).stream():
            payload = snapshot.to_dict() or {}
            existing_id = _safe_str(payload.get("id") or snapshot.id)
            if existing_id:
                return existing_id
    record_id = f"cmp_demo_{int(workspace_id)}"
    payload = {
        "id": record_id,
        "user_id": int(user_id),
        "paper_ids": [int(value) for value in paper_ids[:3]],
        "optional_context": "Demo onboarding comparison",
        "fingerprint": fingerprint,
        "result": {
            "summary": (
                "Paper 1 reports strong factual precision gains, while Paper 2 shows those gains "
                "degrade under distribution shift. Paper 3 mitigates this with re-ranking."
            ),
            "contradictions": [
                "Generalization improves in one study but regresses in out-of-distribution cohorts.",
            ],
            "recommendations": [
                "Compare benchmark split definitions before claiming robustness gains.",
            ],
            "demo": True,
        },
        "created_at": _utcnow(),
    }
    if hasattr(repo, "create_paper_comparison"):
        try:
            record = repo.create_paper_comparison(
                id=record_id,
                user_id=int(user_id),
                paper_ids=[int(value) for value in paper_ids[:3]],
                optional_context="Demo onboarding comparison",
                fingerprint=fingerprint,
                result=payload["result"],
            )
            return str(record.id)
        except Exception:
            pass
    if collection is not None:
        collection.document(record_id).set(payload, merge=True)
    return record_id


def _seed_demo_report(
    *,
    repo: ResearchRepository,
    user_id: int,
    paper_ids: Sequence[int],
    workspace_id: int,
) -> str:
    fingerprint = f"demo:onboarding:report:{int(workspace_id)}"
    existing_id = ""
    if hasattr(repo, "find_research_report_by_fingerprint"):
        try:
            existing = repo.find_research_report_by_fingerprint(fingerprint)
            if existing:
                return str(existing.id)
        except Exception:
            pass
    collection = _collection(repo, "research_reports")
    if collection is not None:
        for snapshot in collection.where(
            filter=FieldFilter("fingerprint", "==", fingerprint)
        ).limit(1).stream():
            payload = snapshot.to_dict() or {}
            existing_id = _safe_str(payload.get("id") or snapshot.id)
            if existing_id:
                return existing_id
    record_id = f"rpt_demo_{int(workspace_id)}"
    result_payload = {
        "summary": (
            "The workspace suggests a clear shift toward retrieval quality controls, while evidence "
            "shows robustness claims depend heavily on domain alignment."
        ),
        "sections": {
            "key_findings": [
                "Evidence reranking improves grounded answer faithfulness.",
                "Distribution shift remains the primary failure mode.",
            ],
            "gaps": [
                "Few studies report cross-institution external validity.",
            ],
            "next_steps": [
                "Run a controlled paper comparison on shift-sensitive metrics.",
            ],
        },
        "demo": True,
    }
    if hasattr(repo, "create_research_report"):
        try:
            record = repo.create_research_report(
                id=record_id,
                user_id=int(user_id),
                paper_ids=[int(value) for value in paper_ids[:5]],
                topic="Demo workspace synthesis",
                fingerprint=fingerprint,
                result=result_payload,
            )
            return str(record.id)
        except Exception:
            pass
    if collection is not None:
        collection.document(record_id).set(
            {
                "id": record_id,
                "user_id": int(user_id),
                "paper_ids": [int(value) for value in paper_ids[:5]],
                "topic": "Demo workspace synthesis",
                "fingerprint": fingerprint,
                "result": result_payload,
                "created_at": _utcnow(),
            },
            merge=True,
        )
    return record_id


def _seed_demo_feed(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: int,
    papers: Sequence[Paper],
) -> int:
    collection = _collection(repo, "workspace_feed")
    if collection is None:
        return 0
    if not papers:
        return 0
    paper_map = {int(getattr(paper, "id", 0) or 0): paper for paper in papers}
    paper_ids = [item for item in paper_map.keys() if item > 0]
    if not paper_ids:
        return 0
    now = _utcnow()
    expires_at = now + timedelta(hours=24)
    fingerprint, _ = build_workspace_feed_fingerprint(
        repo=repo,
        workspace_id=int(workspace_id),
        user_id=int(user_id),
    )

    def _source_for(paper_id: int, source_index: int) -> Dict[str, Any]:
        paper = paper_map.get(int(paper_id))
        if paper is None:
            return {
                "source_index": int(source_index),
                "source_id": f"paper:{int(paper_id)}",
                "source_type": "paper",
                "title": f"Paper {int(paper_id)}",
                "url": "",
                "doi": "",
                "paper_id": int(paper_id),
                "similarity_score": 0.75,
            }
        return {
            "source_index": int(source_index),
            "source_id": f"paper:{int(paper_id)}",
            "source_type": "paper",
            "title": _safe_str(getattr(paper, "title", "")) or f"Paper {int(paper_id)}",
            "url": _safe_str(getattr(paper, "url", "")),
            "doi": _safe_str(getattr(paper, "doi", "")),
            "paper_id": int(paper_id),
            "similarity_score": 0.8 - (source_index * 0.05),
        }

    primary = paper_ids[0]
    secondary = paper_ids[1] if len(paper_ids) > 1 else paper_ids[0]
    tertiary = paper_ids[2] if len(paper_ids) > 2 else secondary
    demo_rows = [
        {
            "feed_item_id": f"demo_feed_{workspace_id}_1",
            "type": "contradiction",
            "title": "New contradiction found between Paper A and B",
            "description": (
                "Robustness claims diverge when the same method is evaluated under domain shift."
            ),
            "related_papers": [primary, secondary],
            "importance_score": 0.93,
            "source_refs": [1, 2],
            "sources": [_source_for(primary, 1), _source_for(secondary, 2)],
        },
        {
            "feed_item_id": f"demo_feed_{workspace_id}_2",
            "type": "trend",
            "title": "Emerging trend: evidence reranking appears in 3 papers",
            "description": (
                "Recent papers consistently tie reranking quality to better grounded answers."
            ),
            "related_papers": [primary, tertiary],
            "importance_score": 0.84,
            "source_refs": [1, 3],
            "sources": [_source_for(primary, 1), _source_for(tertiary, 3)],
        },
        {
            "feed_item_id": f"demo_feed_{workspace_id}_3",
            "type": "recommendation",
            "title": "You should compare these two papers",
            "description": (
                "Run Compare Papers to inspect assumptions behind contradictory reliability outcomes."
            ),
            "related_papers": [secondary, tertiary],
            "importance_score": 0.79,
            "source_refs": [2, 3],
            "sources": [_source_for(secondary, 2), _source_for(tertiary, 3)],
        },
    ]
    count = 0
    for row in demo_rows:
        payload = {
            **row,
            "task_type": "workspace_feed",
            "workspace_id": int(workspace_id),
            "user_id": int(user_id),
            "read": False,
            "read_at": None,
            "created_at": now,
            "updated_at": now,
            "generated_at": now,
            "expires_at": expires_at,
            "fingerprint": fingerprint,
            "trigger": "onboarding_demo",
            "job_id": "demo_bootstrap",
            "archived": False,
            "disclaimer": WORKSPACE_FEED_DISCLAIMER,
        }
        collection.document(_safe_str(row["feed_item_id"])).set(payload, merge=True)
        count += 1
    return count


def _seed_demo_insights(
    *,
    repo: ResearchRepository,
    workspace_id: int,
    user_id: int,
    papers: Sequence[Paper],
) -> Optional[str]:
    collection = _collection(repo, "workspace_insights")
    if collection is None:
        return None
    paper_rows = [paper for paper in papers if int(getattr(paper, "id", 0) or 0) > 0][:4]
    if not paper_rows:
        return None
    now = _utcnow()
    insight_id = f"demo_insight_{int(workspace_id)}"
    sources: List[Dict[str, Any]] = []
    for idx, paper in enumerate(paper_rows, start=1):
        sources.append(
            {
                "source_index": idx,
                "source_id": f"paper:{int(getattr(paper, 'id', 0) or 0)}",
                "source_type": "paper",
                "title": _safe_str(getattr(paper, "title", "")) or f"Paper {idx}",
                "url": _safe_str(getattr(paper, "url", "")),
                "doi": _safe_str(getattr(paper, "doi", "")),
                "similarity_score": 0.84 - (idx * 0.05),
            }
        )
    payload = {
        "key_themes": [
            {
                "text": "Retrieval quality is the dominant driver of trustworthy answer generation in this scenario.",
                "source_refs": [1, 2],
            }
        ],
        "emerging_trends": [
            {
                "text": "Evidence reranking is repeatedly used to reduce unsupported claims without large latency cost.",
                "source_refs": [1, 3],
            }
        ],
        "contradictions": [
            {
                "text": "Robustness outcomes conflict when models are evaluated under institution-level distribution shift.",
                "source_refs": [2, 3],
            }
        ],
        "important_findings": [
            {
                "text": "Faithfulness improves when the assistant narrows context to verified high-relevance chunks.",
                "source_refs": [1, 3],
            }
        ],
        "research_gaps": [
            {
                "text": "Few studies report cross-site external validity and shift-aware calibration metrics.",
                "source_refs": [2],
            }
        ],
        "recommended_next_steps": [
            {
                "text": "Run controlled side-by-side comparisons using the same benchmark splits before claiming superiority.",
                "source_refs": [1, 2, 3],
            }
        ],
    }
    collection.document(insight_id).set(
        {
            "insight_id": insight_id,
            "workspace_id": int(workspace_id),
            "user_id": int(user_id),
            "task_type": "workspace_insights",
            "status": "completed",
            "confidence": 0.88,
            "disclaimer": WORKSPACE_INSIGHTS_DISCLAIMER,
            "sources": sources,
            "payload": payload,
            "generated_at": now,
            "expires_at": now + timedelta(hours=24),
            "updated_at": now,
            "trigger": "onboarding_demo",
            "fingerprint": f"demo:onboarding:insight:{int(workspace_id)}",
            "job_id": "demo_bootstrap",
        },
        merge=True,
    )
    return insight_id


def bootstrap_demo_workspace(
    *,
    repo: ResearchRepository,
    user: User,
    workspace_id: Optional[int] = None,
) -> Dict[str, Any]:
    workspace = _resolve_workspace(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=workspace_id,
        create_default=True,
    )
    existing = repo.list_papers_for_workspace(int(workspace.id))
    created_paper_ids: List[int] = []
    demo_paper_ids: List[int] = []
    for paper_seed in DEMO_PAPERS:
        found = _find_demo_paper(
            papers=existing,
            target_title=_safe_str(paper_seed.get("title")),
            target_doi=_safe_str(paper_seed.get("doi")),
        )
        if found is None:
            created = repo.create_paper(
                workspace_id=int(workspace.id),
                title=_safe_str(paper_seed.get("title")),
                authors=_safe_str(paper_seed.get("authors")),
                abstract=_safe_str(paper_seed.get("abstract")),
                url=_safe_str(paper_seed.get("url")) or None,
            )
            created.doi = _safe_str(paper_seed.get("doi")) or None
            created.source = _safe_str(paper_seed.get("source")) or "demo_seed"
            created.access_type = "open_access"
            created.full_text_available = True
            repo.save(created)
            found = created
            created_paper_ids.append(int(found.id or 0))
            existing.append(found)
        if int(found.id or 0) > 0:
            demo_paper_ids.append(int(found.id or 0))

    demo_paper_ids = [paper_id for paper_id in demo_paper_ids if paper_id > 0]
    comparison_id = _seed_demo_comparison(
        repo=repo,
        user_id=int(user.id or 0),
        paper_ids=demo_paper_ids,
        workspace_id=int(workspace.id),
    )
    report_id = _seed_demo_report(
        repo=repo,
        user_id=int(user.id or 0),
        paper_ids=demo_paper_ids,
        workspace_id=int(workspace.id),
    )
    feed_seed_count = _seed_demo_feed(
        repo=repo,
        workspace_id=int(workspace.id),
        user_id=int(user.id or 0),
        papers=existing,
    )
    insight_id = _seed_demo_insights(
        repo=repo,
        workspace_id=int(workspace.id),
        user_id=int(user.id or 0),
        papers=existing,
    )

    state = _read_state(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=int(workspace.id),
    )
    completed_steps = _load_completed_steps(state.get("completed_steps") or [])
    if ONBOARDING_STEP_UPLOAD not in completed_steps:
        completed_steps.append(ONBOARDING_STEP_UPLOAD)
    _persist_state(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=int(workspace.id),
        payload={
            "created_at": state.get("created_at") or _utcnow(),
            "demo_seeded": True,
            "demo_seeded_at": _utcnow(),
            "demo_paper_ids": demo_paper_ids[:6],
            "completed_steps": completed_steps,
            "dismissed": False,
        },
        merge=True,
    )

    flags = dict(getattr(user, "feature_flags", {}) or {})
    if bool(flags.get("onboarding_dismissed")):
        flags["onboarding_dismissed"] = False
        user.feature_flags = flags
        repo.save(user)
        _invalidate_user_cache(_safe_str(getattr(user, "email", "")))

    status = get_onboarding_status(
        repo=repo,
        user=user,
        workspace_id=int(workspace.id),
    )
    return {
        "workspace_id": int(workspace.id),
        "workspace_name": _safe_str(workspace.name),
        "created_paper_ids": created_paper_ids,
        "paper_ids": demo_paper_ids,
        "comparison_id": comparison_id,
        "report_id": report_id,
        "insight_id": insight_id,
        "seeded_feed_items": int(feed_seed_count),
        "status": status,
    }


def mark_step_best_effort(
    *,
    repo: ResearchRepository,
    user_id: int,
    workspace_id: int,
    step_id: str,
) -> None:
    try:
        user = repo.get_user_by_id(int(user_id))
        if user is None:
            return
        record_onboarding_step(
            repo=repo,
            user=user,
            workspace_id=int(workspace_id),
            step_id=step_id,
        )
    except Exception as exc:
        logger.debug(
            "Skipping onboarding step tracking user_id=%s workspace_id=%s step=%s error=%s",
            user_id,
            workspace_id,
            step_id,
            exc,
        )


def reset_onboarding_memory_state() -> None:
    with _IN_MEMORY_LOCK:
        _IN_MEMORY_ONBOARDING.clear()
