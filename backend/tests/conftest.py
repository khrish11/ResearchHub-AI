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
    r.data_rights_requests = emulator_db.collection("data_rights_requests")
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
    "data_rights_requests",
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
    for col in _COLLECTIONS_TO_WIPE:
        _delete_collection(emulator_db.collection(col))
    yield
    for col in _COLLECTIONS_TO_WIPE:
        _delete_collection(emulator_db.collection(col))


# ─────────────────────────────────────────────────────────────────────────────
# Mock user & auth token
# ─────────────────────────────────────────────────────────────────────────────

TEST_USER_EMAIL = "testuser@soyogai.test"


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
def auth_headers(mock_user: User) -> dict:
    """Return Authorization headers with a valid JWT for the test user."""
    token = create_access_token(
        {"sub": mock_user.email}, expires_delta=timedelta(hours=1)
    )
    return {"Authorization": f"Bearer {token}"}


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
