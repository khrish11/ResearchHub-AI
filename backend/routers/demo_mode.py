from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from repositories import ResearchRepository, get_research_repository
from repositories.research import User
from routers.auth import get_current_user
from services.demo_mode_service import (
    complete_demo_mode_step,
    exit_demo_mode,
    get_demo_mode_state,
    advance_demo_mode_step,
    start_demo_mode,
)


router = APIRouter(prefix="/demo", tags=["demo"])


class DemoModeStepOut(BaseModel):
    id: str
    index: int
    title: str
    what_happening: str
    why_matters: str
    action_label: str
    action_path: str
    target_key: str
    tooltip: str
    completed: bool = False
    active: bool = False


class DemoStateResponse(BaseModel):
    is_demo_mode: bool = False
    workspace_id: int
    workspace_name: str = ""
    scenario_title: str = ""
    story_intro: str = ""
    progress: float = 0.0
    current_step: Optional[str] = None
    completed_steps: List[str] = Field(default_factory=list)
    steps: List[DemoModeStepOut] = Field(default_factory=list)
    demo_seeded: bool = False
    demo_seeded_at: Optional[str] = None
    paper_count: int = 0
    comparison_id: Optional[str] = None
    report_id: Optional[str] = None
    insight_id: Optional[str] = None
    started_at: Optional[str] = None
    exited_at: Optional[str] = None
    bootstrap: Optional[Dict[str, Any]] = None


class DemoStartRequest(BaseModel):
    workspace_id: Optional[int] = None


class DemoStepCompleteRequest(BaseModel):
    workspace_id: int
    step_id: str


class DemoStepAdvanceRequest(BaseModel):
    workspace_id: int


class DemoExitRequest(BaseModel):
    workspace_id: Optional[int] = None


def _map_demo_state(payload: Dict[str, Any]) -> DemoStateResponse:
    return DemoStateResponse(
        is_demo_mode=bool(payload.get("is_demo_mode")),
        workspace_id=int(payload.get("workspace_id") or 0),
        workspace_name=str(payload.get("workspace_name") or ""),
        scenario_title=str(payload.get("scenario_title") or ""),
        story_intro=str(payload.get("story_intro") or ""),
        progress=float(payload.get("progress") or 0.0),
        current_step=str(payload.get("current_step") or "") or None,
        completed_steps=[str(step) for step in (payload.get("completed_steps") or []) if str(step).strip()],
        steps=[
            DemoModeStepOut(
                id=str(step.get("id") or ""),
                index=int(step.get("index") or 0),
                title=str(step.get("title") or ""),
                what_happening=str(step.get("what_happening") or ""),
                why_matters=str(step.get("why_matters") or ""),
                action_label=str(step.get("action_label") or ""),
                action_path=str(step.get("action_path") or ""),
                target_key=str(step.get("target_key") or ""),
                tooltip=str(step.get("tooltip") or ""),
                completed=bool(step.get("completed")),
                active=bool(step.get("active")),
            )
            for step in (payload.get("steps") or [])
            if isinstance(step, dict)
        ],
        demo_seeded=bool(payload.get("demo_seeded")),
        demo_seeded_at=(str(payload.get("demo_seeded_at") or "") or None),
        paper_count=int(payload.get("paper_count") or 0),
        comparison_id=str(payload.get("comparison_id") or "") or None,
        report_id=str(payload.get("report_id") or "") or None,
        insight_id=str(payload.get("insight_id") or "") or None,
        started_at=str(payload.get("started_at") or "") or None,
        exited_at=str(payload.get("exited_at") or "") or None,
        bootstrap=payload.get("bootstrap") if isinstance(payload.get("bootstrap"), dict) else None,
    )


@router.get("/state", response_model=DemoStateResponse)
def demo_state(
    workspace_id: Optional[int] = None,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> DemoStateResponse:
    try:
        payload = get_demo_mode_state(
            repo=repo,
            user=current_user,
            workspace_id=workspace_id,
        )
        return _map_demo_state(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/start", response_model=DemoStateResponse)
def start_demo(
    request: DemoStartRequest,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> DemoStateResponse:
    try:
        payload = start_demo_mode(
            repo=repo,
            user=current_user,
            workspace_id=request.workspace_id,
        )
        return _map_demo_state(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/steps/complete", response_model=DemoStateResponse)
def complete_demo_step(
    request: DemoStepCompleteRequest,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> DemoStateResponse:
    try:
        payload = complete_demo_mode_step(
            repo=repo,
            user=current_user,
            workspace_id=int(request.workspace_id),
            step_id=request.step_id,
        )
        return _map_demo_state(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/steps/next", response_model=DemoStateResponse)
def advance_demo_step(
    request: DemoStepAdvanceRequest,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> DemoStateResponse:
    try:
        payload = advance_demo_mode_step(
            repo=repo,
            user=current_user,
            workspace_id=int(request.workspace_id),
        )
        return _map_demo_state(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/exit", response_model=DemoStateResponse)
def exit_demo(
    request: DemoExitRequest,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> DemoStateResponse:
    try:
        payload = exit_demo_mode(
            repo=repo,
            user=current_user,
            workspace_id=request.workspace_id,
        )
        return _map_demo_state(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

