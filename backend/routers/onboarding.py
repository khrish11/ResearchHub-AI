from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from repositories import ResearchRepository, get_research_repository
from repositories.research import User
from routers.auth import get_current_user
from services.onboarding_service import (
    ONBOARDING_STEP_ORDER,
    bootstrap_demo_workspace,
    get_onboarding_status,
    record_onboarding_step,
    set_onboarding_dismissed,
)


router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class OnboardingStepOut(BaseModel):
    id: str
    title: str
    description: str
    action_label: str
    action_path: str
    completed: bool = False


class OnboardingDemoPreviewPaper(BaseModel):
    title: str
    authors: str


class OnboardingDemoPreviewItem(BaseModel):
    type: str
    title: str
    description: str
    importance_score: float = 0.0


class OnboardingDemoOut(BaseModel):
    available: bool = True
    seeded: bool = False
    seeded_at: Optional[str] = None
    paper_ids: List[int] = Field(default_factory=list)
    sample_papers: List[OnboardingDemoPreviewPaper] = Field(default_factory=list)
    sample_comparison: Dict[str, str] = Field(default_factory=dict)
    sample_report: Dict[str, str] = Field(default_factory=dict)
    sample_feed_items: List[OnboardingDemoPreviewItem] = Field(default_factory=list)


class OnboardingStatusResponse(BaseModel):
    workspace_id: int
    workspace_name: str = ""
    paper_count: int = 0
    has_completed_onboarding: bool = False
    dismissed: bool = False
    needs_onboarding: bool = False
    progress: float = 0.0
    completed_steps: List[str] = Field(default_factory=list)
    steps: List[OnboardingStepOut] = Field(default_factory=list)
    copilot_prompts: List[str] = Field(default_factory=list)
    demo: OnboardingDemoOut = Field(default_factory=OnboardingDemoOut)


class DemoBootstrapRequest(BaseModel):
    workspace_id: Optional[int] = None


class DismissOnboardingRequest(BaseModel):
    workspace_id: Optional[int] = None
    dismissed: bool = True


class CompleteOnboardingStepRequest(BaseModel):
    workspace_id: int


class DemoBootstrapResponse(BaseModel):
    workspace_id: int
    workspace_name: str
    created_paper_ids: List[int] = Field(default_factory=list)
    paper_ids: List[int] = Field(default_factory=list)
    comparison_id: Optional[str] = None
    report_id: Optional[str] = None
    seeded_feed_items: int = 0
    status: OnboardingStatusResponse


def _map_status(payload: Dict[str, Any]) -> OnboardingStatusResponse:
    return OnboardingStatusResponse(
        workspace_id=int(payload.get("workspace_id") or 0),
        workspace_name=str(payload.get("workspace_name") or ""),
        paper_count=int(payload.get("paper_count") or 0),
        has_completed_onboarding=bool(payload.get("has_completed_onboarding")),
        dismissed=bool(payload.get("dismissed")),
        needs_onboarding=bool(payload.get("needs_onboarding")),
        progress=float(payload.get("progress") or 0.0),
        completed_steps=[
            str(step)
            for step in (payload.get("completed_steps") or [])
            if str(step) in ONBOARDING_STEP_ORDER
        ],
        steps=[
            OnboardingStepOut(
                id=str(step.get("id") or ""),
                title=str(step.get("title") or ""),
                description=str(step.get("description") or ""),
                action_label=str(step.get("action_label") or ""),
                action_path=str(step.get("action_path") or ""),
                completed=bool(step.get("completed")),
            )
            for step in (payload.get("steps") or [])
            if isinstance(step, dict)
        ],
        copilot_prompts=[
            str(item)
            for item in (payload.get("copilot_prompts") or [])
            if str(item).strip()
        ][:8],
        demo=OnboardingDemoOut(
            available=bool((payload.get("demo") or {}).get("available", True)),
            seeded=bool((payload.get("demo") or {}).get("seeded")),
            seeded_at=((payload.get("demo") or {}).get("seeded_at")),
            paper_ids=[
                int(item)
                for item in ((payload.get("demo") or {}).get("paper_ids") or [])
                if int(item) > 0
            ],
            sample_papers=[
                OnboardingDemoPreviewPaper(
                    title=str(item.get("title") or ""),
                    authors=str(item.get("authors") or ""),
                )
                for item in ((payload.get("demo") or {}).get("sample_papers") or [])
                if isinstance(item, dict)
            ],
            sample_comparison={
                "title": str(((payload.get("demo") or {}).get("sample_comparison") or {}).get("title") or ""),
                "description": str(
                    ((payload.get("demo") or {}).get("sample_comparison") or {}).get("description") or ""
                ),
            },
            sample_report={
                "title": str(((payload.get("demo") or {}).get("sample_report") or {}).get("title") or ""),
                "description": str(((payload.get("demo") or {}).get("sample_report") or {}).get("description") or ""),
            },
            sample_feed_items=[
                OnboardingDemoPreviewItem(
                    type=str(item.get("type") or "recommendation"),
                    title=str(item.get("title") or ""),
                    description=str(item.get("description") or ""),
                    importance_score=float(item.get("importance_score") or 0.0),
                )
                for item in ((payload.get("demo") or {}).get("sample_feed_items") or [])
                if isinstance(item, dict)
            ],
        ),
    )


@router.get("/status", response_model=OnboardingStatusResponse)
def onboarding_status(
    workspace_id: Optional[int] = None,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> OnboardingStatusResponse:
    try:
        status = get_onboarding_status(
            repo=repo,
            user=current_user,
            workspace_id=workspace_id,
        )
        return _map_status(status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/demo/bootstrap", response_model=DemoBootstrapResponse)
def bootstrap_demo(
    payload: DemoBootstrapRequest,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> DemoBootstrapResponse:
    try:
        result = bootstrap_demo_workspace(
            repo=repo,
            user=current_user,
            workspace_id=payload.workspace_id,
        )
        return DemoBootstrapResponse(
            workspace_id=int(result.get("workspace_id") or 0),
            workspace_name=str(result.get("workspace_name") or ""),
            created_paper_ids=[int(item) for item in (result.get("created_paper_ids") or []) if int(item) > 0],
            paper_ids=[int(item) for item in (result.get("paper_ids") or []) if int(item) > 0],
            comparison_id=str(result.get("comparison_id") or "") or None,
            report_id=str(result.get("report_id") or "") or None,
            seeded_feed_items=int(result.get("seeded_feed_items") or 0),
            status=_map_status(result.get("status") if isinstance(result.get("status"), dict) else {}),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/dismiss", response_model=OnboardingStatusResponse)
def dismiss_onboarding(
    payload: DismissOnboardingRequest,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> OnboardingStatusResponse:
    status = set_onboarding_dismissed(
        repo=repo,
        user=current_user,
        workspace_id=payload.workspace_id,
        dismissed=bool(payload.dismissed),
    )
    return _map_status(status)


@router.post("/steps/{step_id}/complete", response_model=OnboardingStatusResponse)
def complete_onboarding_step(
    step_id: str,
    payload: CompleteOnboardingStepRequest,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
) -> OnboardingStatusResponse:
    try:
        status = record_onboarding_step(
            repo=repo,
            user=current_user,
            workspace_id=int(payload.workspace_id),
            step_id=step_id,
        )
        return _map_status(status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

