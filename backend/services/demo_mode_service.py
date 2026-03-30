from __future__ import annotations

import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Sequence, Tuple

from repositories import ResearchRepository
from repositories.research import User, Workspace
from services.onboarding_service import bootstrap_demo_workspace


logger = logging.getLogger(__name__)

DEMO_STEP_EXPLAIN = "explain_paper"
DEMO_STEP_COMPARE = "compare_papers"
DEMO_STEP_REPORT = "generate_report"
DEMO_STEP_INSIGHTS = "view_insights"
DEMO_STEP_COPILOT = "use_copilot"
DEMO_STEP_ORDER: Tuple[str, ...] = (
    DEMO_STEP_EXPLAIN,
    DEMO_STEP_COMPARE,
    DEMO_STEP_REPORT,
    DEMO_STEP_INSIGHTS,
    DEMO_STEP_COPILOT,
)

DEMO_SCENARIO_TITLE = "Clinical RAG Reliability Under Distribution Shift"
DEMO_STORY_INTRO = (
    "This guided demo shows how Soyog AI moves from paper understanding to cross-paper decisions "
    "using grounded context and transparent evidence links."
)

DEMO_STEP_META: Dict[str, Dict[str, str]] = {
    DEMO_STEP_EXPLAIN: {
        "title": "Explain a paper",
        "what_happening": "Soyog AI distills a complex paper into a clear explanation with method and evidence quality.",
        "why_matters": "Teams align faster when they understand claims, assumptions, and limitations in seconds.",
        "action_label": "Open paper explanation",
        "action_path": "/workspace/{workspace_id}?demo=1",
        "target_key": "workspaces",
        "tooltip": "Open any seeded paper and inspect the AI explanation panel.",
    },
    DEMO_STEP_COMPARE: {
        "title": "Compare two papers",
        "what_happening": "The system highlights convergences and contradictions between two studies.",
        "why_matters": "Comparison prevents cherry-picking and reveals where evidence actually disagrees.",
        "action_label": "Run comparison",
        "action_path": "/compare?workspace_id={workspace_id}&demo=1",
        "target_key": "demo_panel",
        "tooltip": "Use compare to validate conflicting robustness claims.",
    },
    DEMO_STEP_REPORT: {
        "title": "Generate a report",
        "what_happening": "Soyog AI assembles a structured synthesis with findings, gaps, and next actions.",
        "why_matters": "You move from scattered reading to decision-ready output without losing traceability.",
        "action_label": "Open report flow",
        "action_path": "/research-report?workspace_id={workspace_id}&demo=1",
        "target_key": "demo_panel",
        "tooltip": "Reports turn workspace context into shareable narratives.",
    },
    DEMO_STEP_INSIGHTS: {
        "title": "View insights",
        "what_happening": "Precomputed insights surface trends, contradictions, and research gaps from the seeded workspace.",
        "why_matters": "Proactive signals help teams prioritize what to investigate next.",
        "action_label": "Focus insights section",
        "action_path": "/dashboard?workspace_id={workspace_id}&demo=1#insights",
        "target_key": "insights",
        "tooltip": "Observe how insights cite source papers for transparency.",
    },
    DEMO_STEP_COPILOT: {
        "title": "Use Copilot",
        "what_happening": "Copilot routes intent to explain, compare, report, or RAG automatically.",
        "why_matters": "Users get expert outcomes from one prompt instead of learning multiple tool surfaces.",
        "action_label": "Ask Copilot",
        "action_path": "/dashboard?workspace_id={workspace_id}&demo=1#copilot",
        "target_key": "copilot",
        "tooltip": "Try prompts like 'What are the main trends?' to see unified routing.",
    },
}

_IN_MEMORY_LOCK = Lock()
_IN_MEMORY_DEMO: Dict[str, Dict[str, Any]] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


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


def _read_demo_state(
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
        row = _IN_MEMORY_DEMO.get(row_id)
        return dict(row) if row else {}


def _persist_demo_state(
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
        current = _IN_MEMORY_DEMO.get(row_id, {})
        if merge:
            merged = dict(current)
            merged.update(record)
            _IN_MEMORY_DEMO[row_id] = merged
        else:
            _IN_MEMORY_DEMO[row_id] = record
        return dict(_IN_MEMORY_DEMO[row_id])


def _normalize_steps(values: Sequence[Any]) -> List[str]:
    rows: List[str] = []
    for value in values:
        step_id = _safe_str(value)
        if step_id in DEMO_STEP_ORDER and step_id not in rows:
            rows.append(step_id)
    return rows


def _next_incomplete_step(completed_steps: Sequence[str]) -> Optional[str]:
    completed_set = set(completed_steps)
    for step_id in DEMO_STEP_ORDER:
        if step_id not in completed_set:
            return step_id
    return None


def _step_rows(
    *,
    workspace_id: int,
    completed_steps: Sequence[str],
    current_step: Optional[str],
) -> List[Dict[str, Any]]:
    completed_set = set(completed_steps)
    rows: List[Dict[str, Any]] = []
    for index, step_id in enumerate(DEMO_STEP_ORDER, start=1):
        meta = DEMO_STEP_META[step_id]
        rows.append(
            {
                "id": step_id,
                "index": index,
                "title": _safe_str(meta.get("title")),
                "what_happening": _safe_str(meta.get("what_happening")),
                "why_matters": _safe_str(meta.get("why_matters")),
                "action_label": _safe_str(meta.get("action_label")),
                "action_path": _safe_str(meta.get("action_path")).format(workspace_id=workspace_id),
                "target_key": _safe_str(meta.get("target_key")),
                "tooltip": _safe_str(meta.get("tooltip")),
                "completed": step_id in completed_set,
                "active": bool(current_step) and step_id == current_step,
            }
        )
    return rows


def _build_demo_payload(
    *,
    repo: ResearchRepository,
    user: User,
    workspace: Workspace,
    state: Dict[str, Any],
) -> Dict[str, Any]:
    completed_steps = _normalize_steps(state.get("demo_mode_completed_steps") or [])
    current_step = _safe_str(state.get("demo_mode_current_step"))
    if current_step not in DEMO_STEP_ORDER:
        current_step = _next_incomplete_step(completed_steps) or DEMO_STEP_ORDER[-1]
    progress = len(completed_steps) / float(len(DEMO_STEP_ORDER))
    enabled = bool(state.get("demo_mode_enabled"))
    paper_count = len(repo.list_papers_for_workspace(int(workspace.id)))
    return {
        "is_demo_mode": bool(enabled),
        "workspace_id": int(workspace.id),
        "workspace_name": _safe_str(workspace.name),
        "scenario_title": DEMO_SCENARIO_TITLE,
        "story_intro": DEMO_STORY_INTRO,
        "progress": round(float(progress), 4),
        "current_step": current_step,
        "completed_steps": completed_steps,
        "steps": _step_rows(
            workspace_id=int(workspace.id),
            completed_steps=completed_steps,
            current_step=current_step if enabled else None,
        ),
        "demo_seeded": bool(state.get("demo_seeded")),
        "demo_seeded_at": _to_iso(state.get("demo_seeded_at")),
        "paper_count": int(paper_count),
        "comparison_id": _safe_str(state.get("demo_comparison_id")) or None,
        "report_id": _safe_str(state.get("demo_report_id")) or None,
        "insight_id": _safe_str(state.get("demo_insight_id")) or None,
        "started_at": _to_iso(state.get("demo_mode_started_at")),
        "exited_at": _to_iso(state.get("demo_mode_exited_at")),
    }


def start_demo_mode(
    *,
    repo: ResearchRepository,
    user: User,
    workspace_id: Optional[int] = None,
) -> Dict[str, Any]:
    seeded = bootstrap_demo_workspace(
        repo=repo,
        user=user,
        workspace_id=workspace_id,
    )
    target_workspace_id = _coerce_int(seeded.get("workspace_id"), 0)
    workspace = _resolve_workspace(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=target_workspace_id,
        create_default=True,
    )
    state = _read_demo_state(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=int(workspace.id),
    )
    completed_steps = _normalize_steps(state.get("demo_mode_completed_steps") or [])
    current_step = _next_incomplete_step(completed_steps) or DEMO_STEP_ORDER[-1]
    now = _utcnow()
    persisted = _persist_demo_state(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=int(workspace.id),
        payload={
            "created_at": state.get("created_at") or now,
            "demo_mode_enabled": True,
            "demo_mode_started_at": state.get("demo_mode_started_at") or now,
            "demo_mode_exited_at": None,
            "demo_mode_current_step": current_step,
            "demo_mode_completed_steps": completed_steps,
            "demo_comparison_id": _safe_str(seeded.get("comparison_id")) or state.get("demo_comparison_id"),
            "demo_report_id": _safe_str(seeded.get("report_id")) or state.get("demo_report_id"),
            "demo_insight_id": _safe_str(seeded.get("insight_id")) or state.get("demo_insight_id"),
            "demo_seeded": True,
            "demo_seeded_at": seeded.get("status", {}).get("demo", {}).get("seeded_at") if isinstance(seeded.get("status"), dict) else now,
        },
        merge=True,
    )
    payload = _build_demo_payload(
        repo=repo,
        user=user,
        workspace=workspace,
        state=persisted,
    )
    payload["bootstrap"] = seeded
    return payload


def get_demo_mode_state(
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
    state = _read_demo_state(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=int(workspace.id),
    )
    return _build_demo_payload(
        repo=repo,
        user=user,
        workspace=workspace,
        state=state,
    )


def complete_demo_mode_step(
    *,
    repo: ResearchRepository,
    user: User,
    workspace_id: int,
    step_id: str,
) -> Dict[str, Any]:
    clean_step = _safe_str(step_id)
    if clean_step not in DEMO_STEP_ORDER:
        raise ValueError("Unsupported demo step.")
    workspace = _resolve_workspace(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=workspace_id,
        create_default=False,
    )
    state = _read_demo_state(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=int(workspace.id),
    )
    completed_steps = _normalize_steps(state.get("demo_mode_completed_steps") or [])
    if clean_step not in completed_steps:
        completed_steps.append(clean_step)
    next_step = _next_incomplete_step(completed_steps)
    now = _utcnow()
    persisted = _persist_demo_state(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=int(workspace.id),
        payload={
            "demo_mode_enabled": True,
            "demo_mode_completed_steps": completed_steps,
            "demo_mode_current_step": next_step or DEMO_STEP_ORDER[-1],
            "demo_mode_completed_at": now if not next_step else None,
            "created_at": state.get("created_at") or now,
        },
        merge=True,
    )
    return _build_demo_payload(
        repo=repo,
        user=user,
        workspace=workspace,
        state=persisted,
    )


def advance_demo_mode_step(
    *,
    repo: ResearchRepository,
    user: User,
    workspace_id: int,
) -> Dict[str, Any]:
    workspace = _resolve_workspace(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=workspace_id,
        create_default=False,
    )
    state = _read_demo_state(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=int(workspace.id),
    )
    completed_steps = _normalize_steps(state.get("demo_mode_completed_steps") or [])
    current_step = _safe_str(state.get("demo_mode_current_step"))
    if current_step in DEMO_STEP_ORDER and current_step not in completed_steps:
        completed_steps.append(current_step)
    next_step = _next_incomplete_step(completed_steps)
    now = _utcnow()
    persisted = _persist_demo_state(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=int(workspace.id),
        payload={
            "demo_mode_enabled": True,
            "demo_mode_completed_steps": completed_steps,
            "demo_mode_current_step": next_step or DEMO_STEP_ORDER[-1],
            "demo_mode_completed_at": now if not next_step else None,
            "created_at": state.get("created_at") or now,
        },
        merge=True,
    )
    return _build_demo_payload(
        repo=repo,
        user=user,
        workspace=workspace,
        state=persisted,
    )


def exit_demo_mode(
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
    state = _read_demo_state(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=int(workspace.id),
    )
    now = _utcnow()
    persisted = _persist_demo_state(
        repo=repo,
        user_id=int(user.id or 0),
        workspace_id=int(workspace.id),
        payload={
            "demo_mode_enabled": False,
            "demo_mode_exited_at": now,
            "demo_mode_current_step": state.get("demo_mode_current_step") or DEMO_STEP_ORDER[0],
            "demo_mode_completed_steps": _normalize_steps(state.get("demo_mode_completed_steps") or []),
            "created_at": state.get("created_at") or now,
        },
        merge=True,
    )
    return _build_demo_payload(
        repo=repo,
        user=user,
        workspace=workspace,
        state=persisted,
    )


def reset_demo_mode_memory_state() -> None:
    with _IN_MEMORY_LOCK:
        _IN_MEMORY_DEMO.clear()

