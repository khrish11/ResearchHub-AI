"""
tests/conftest.py — shared pytest fixtures for all test modules.

Key design:
- We do NOT initialize firebase-admin for the Firestore client at all.
  Instead we construct a raw google.cloud.firestore.Client with
  AnonymousCredentials — the emulator ignores auth tokens entirely.
- FirebaseResearchRepository is injected directly with this emulator client.
- `clean_db` auto-wipes all collections before each test.
"""

from __future__ import annotations

import os
import threading
from datetime import timedelta, timezone
from typing import Generator

import pytest
from google.auth.credentials import AnonymousCredentials
from google.cloud import firestore as _firestore

from repositories.research import (
    FirebaseResearchRepository,
    User,
    Workspace,
    Paper,
    SearchHistory,
)
from services.cache_service import clear_memory_cache
from services.demo_mode_service import reset_demo_mode_memory_state
from services.onboarding_service import reset_onboarding_memory_state
from services.workspace_feed_service import reset_workspace_feed_memory_state
from routers.auth import create_access_token


# ─────────────────────────────────────────────────────────────────────────────
# Emulator Firestore client
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def emulator_db() -> _firestore.Client:
    """
    Create a Firestore client pointed at the local emulator.
    AnonymousCredentials satisfy the google-auth library without
    triggering any network calls — the emulator accepts any token.
    """
    # Set the emulator host environment variable before creating the client
    os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8081"
    return _firestore.Client(
        project=os.environ["FIREBASE_PROJECT_ID"],
        credentials=AnonymousCredentials(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Repository fixture
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def repo(emulator_db: _firestore.Client) -> FirebaseResearchRepository:
    """Return a FirebaseResearchRepository wired to the emulator.

    Attribute names must exactly match FirebaseResearchRepository.__init__.
    """
    r = object.__new__(FirebaseResearchRepository)
    # `self.db` is used by _next_id and other methods — must match __init__
    r.db = emulator_db
    r._lock = threading.Lock()
    r.users = emulator_db.collection("users")
    r.workspaces = emulator_db.collection("workspaces")
    r.papers = emulator_db.collection("papers")
    r.chats = emulator_db.collection("chats")
    r.search_history = emulator_db.collection("search_history")
    # session state collection is named `user_session_state` in the real code
    r.user_session_state = emulator_db.collection("user_session_state")
    r.workspace_documents = emulator_db.collection("workspace_documents")
    r.workspace_files = emulator_db.collection("workspace_files")
    r.paper_check_jobs = emulator_db.collection("paper_check_jobs")
    r.paper_comparisons = emulator_db.collection("paper_comparisons")
    r.research_reports = emulator_db.collection("research_reports")
    r.data_rights_requests = emulator_db.collection("data_rights_requests")
    r.research_intelligence_artifacts = emulator_db.collection("research_intelligence_artifacts")
    r.saved_research_questions = emulator_db.collection("saved_research_questions")
    r.research_plans = emulator_db.collection("research_plans")
    r.counters = emulator_db.collection("_counters")
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Clean database between tests
# ─────────────────────────────────────────────────────────────────────────────

_COLLECTIONS_TO_WIPE = [
    "users",
    "workspaces",
    "papers",
    "chats",
    "search_history",
    "user_session_state",
    "workspace_documents",
    "workspace_files",
    "paper_check_jobs",
    "paper_comparisons",
    "research_reports",
    "paper_explanations",
    "ai_cache",
    "workspace_vectors",
    "workspace_onboarding",
    "workspace_insights",
    "workspace_insight_jobs",
    "workspace_feed",
    "workspace_feed_jobs",
    "data_rights_requests",
    "research_intelligence_artifacts",
    "saved_research_questions",
    "research_plans",
    "_counters",
]


def _delete_collection(
    col_ref: _firestore.CollectionReference, batch_size: int = 50
) -> None:
    docs = list(col_ref.limit(batch_size).stream())
    for doc in docs:
        doc.reference.delete()
    if len(docs) >= batch_size:
        _delete_collection(col_ref, batch_size)


@pytest.fixture(autouse=True)
def clean_db(emulator_db: _firestore.Client) -> Generator[None, None, None]:
    """Wipe all collections before each test for full isolation."""
    clear_memory_cache()
    reset_demo_mode_memory_state()
    reset_onboarding_memory_state()
    reset_workspace_feed_memory_state()
    for col in _COLLECTIONS_TO_WIPE:
        _delete_collection(emulator_db.collection(col))
    yield
    clear_memory_cache()
    reset_demo_mode_memory_state()
    reset_onboarding_memory_state()
    reset_workspace_feed_memory_state()
    for col in _COLLECTIONS_TO_WIPE:
        _delete_collection(emulator_db.collection(col))


# ─────────────────────────────────────────────────────────────────────────────
# Mock user & auth token
# ─────────────────────────────────────────────────────────────────────────────

TEST_USER_EMAIL = "testuser@soyogai.test"
TEST_USER_B_EMAIL = "testuserb@soyogai.test"


@pytest.fixture()
def mock_user(repo: FirebaseResearchRepository) -> User:
    """Create a test user in the emulator and return the User object."""
    return repo.create_user(
        email=TEST_USER_EMAIL,
        name="Test User",
        is_active=True,
        is_verified=True,
    )


@pytest.fixture()
def mock_user_b(repo: FirebaseResearchRepository) -> User:
    """Create a second test user in the emulator for cross-user tests."""
    return repo.create_user(
        email=TEST_USER_B_EMAIL,
        name="Test User B",
        is_active=True,
        is_verified=True,
    )


@pytest.fixture()
def auth_headers(mock_user: User) -> dict:
    """Return Authorization headers with a valid JWT for the test user."""
    token = create_access_token(
        {"sub": mock_user.email}, expires_delta=timedelta(hours=1)
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_a_token(mock_user: User) -> str:
    """Return a JWT token for user A."""
    return create_access_token(
        {"sub": mock_user.email}, expires_delta=timedelta(hours=1)
    )


@pytest.fixture()
def user_b_token(mock_user_b: User) -> str:
    """Return a JWT token for user B."""
    return create_access_token(
        {"sub": mock_user_b.email}, expires_delta=timedelta(hours=1)
    )


@pytest.fixture()
def user_a_workspace(repo: FirebaseResearchRepository, mock_user: User) -> Workspace:
    """Create a workspace for user A."""
    return repo.create_workspace(
        user_id=mock_user.id,
        name="User A Workspace",
        description="Workspace for user A",
    )


@pytest.fixture()
def user_b_workspace(repo: FirebaseResearchRepository, mock_user_b: User) -> Workspace:
    """Create a workspace for user B."""
    return repo.create_workspace(
        user_id=mock_user_b.id,
        name="User B Workspace",
        description="Workspace for user B",
    )


@pytest.fixture()
def user_b_artifact_id(repo: FirebaseResearchRepository, user_b_workspace: Workspace) -> str:
    """Create a research intelligence artifact for user B."""
    from repositories.research import ResearchIntelligenceArtifact
    # Create artifact with minimal required fields
    artifact = repo.create_research_intelligence_artifact(
        id="test_artifact_b",
        workspace_id=user_b_workspace.id,
        user_id=user_b_workspace.user_id,
        topic="Test topic",
        paper_ids=[],
        status="completed",
    )
    # Update with additional fields
    repo.update_research_intelligence_artifact(
        artifact.id,
        {
            "evidence_analysis": {"test": "data"},
            "gap_analysis": {"test": "data"},
            "opportunity_ranking": {"test": "data"},
            "research_questions": {"test": "data"},
            "hypothesis_challenges": {"test": "data"},
            "citation_verification": {"test": "data"},
            "knowledge_graph": {"test": "data"},
            "overall_score": 85,
            "summary": "Test artifact for user B",
        }
    )
    return artifact.id


@pytest.fixture()
def user_b_question_id(repo: FirebaseResearchRepository, user_b_workspace: Workspace) -> str:
    """Create a saved research question for user B."""
    from repositories.research import SavedResearchQuestion
    question = repo.create_saved_research_question(
        id="test_question_b",
        workspace_id=user_b_workspace.id,
        user_id=user_b_workspace.user_id,
        question="Test question for user B",
        category="exploratory",
        complexity="medium",
        confidence=80,
        novelty=85,
        feasibility=75,
        impact=90,
        rationale="Test rationale",
    )
    return question.id


@pytest.fixture()
def user_b_plan_id(repo: FirebaseResearchRepository, user_b_workspace: Workspace, user_b_artifact_id: str) -> str:
    """Create a research plan for user B."""
    from repositories.research import ResearchPlan
    plan = repo.create_research_plan(
        id="test_plan_b",
        workspace_id=user_b_workspace.id,
        user_id=user_b_workspace.user_id,
        artifact_id=user_b_artifact_id,
        opportunity_id="test_opportunity_id",
        opportunity_description="Test opportunity",
        title="Test Plan for User B",
        research_problem="Test problem",
        research_question="Test question",
        hypothesis="Test hypothesis",
        objectives="Test objectives",
        proposed_methodology="Test methodology",
        alternative_methodology="Test alternative",
        datasets="Test datasets",
        variables="Test variables",
        baselines="Test baselines",
        evaluation_metrics="Test metrics",
        expected_contribution="Test contribution",
        risks="Test risks",
        limitations="Test limitations",
        reproducibility_requirements="Test reproducibility",
    )
    return plan.id


@pytest.fixture()
def user_b_workspace_id(user_b_workspace: Workspace) -> int:
    """Return user B's workspace ID."""
    return user_b_workspace.id


@pytest.fixture()
def workspace_a_artifact_id(repo: FirebaseResearchRepository, user_a_workspace: Workspace) -> str:
    """Create a research intelligence artifact for workspace A."""
    from repositories.research import ResearchIntelligenceArtifact
    # Create artifact with minimal required fields
    artifact = repo.create_research_intelligence_artifact(
        id="test_artifact_a",
        workspace_id=user_a_workspace.id,
        user_id=user_a_workspace.user_id,
        topic="Test topic",
        paper_ids=[],
        status="completed",
    )
    # Update with additional fields
    repo.update_research_intelligence_artifact(
        artifact.id,
        {
            "evidence_analysis": {"test": "data"},
            "gap_analysis": {"test": "data"},
            "opportunity_ranking": {"test": "data"},
            "research_questions": {"test": "data"},
            "hypothesis_challenges": {"test": "data"},
            "citation_verification": {"test": "data"},
            "knowledge_graph": {"test": "data"},
            "overall_score": 85,
            "summary": "Test artifact for workspace A",
        }
    )
    return artifact.id


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI TestClient
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def test_client(repo: FirebaseResearchRepository):
    """FastAPI TestClient wired to the app with the emulator repo injected.

    Injects the emulator repo into app.state._repo so that _research_repo()
    (which is called directly by route handlers, not through FastAPI Depends)
    picks up the test repo instead of creating a new FirebaseResearchRepository.
    """
    from fastapi.testclient import TestClient
    from main import app
    from repositories import get_research_repository

    app.dependency_overrides[get_research_repository] = lambda: repo
    app.state._repo = repo

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    app.dependency_overrides.pop(get_research_repository, None)
