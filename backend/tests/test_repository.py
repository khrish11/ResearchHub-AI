"""
tests/test_repository.py — Unit tests for FirebaseResearchRepository.

All writes go to the local Firestore Emulator (see conftest.py).
Tests are fully isolated: `clean_db` fixture wipes collections before and after each test.
"""

from __future__ import annotations

import pytest

from repositories.research import (
    FirebaseResearchRepository,
    User,
    Workspace,
    Paper,
    SearchHistory,
    UserSessionState,
    WorkspaceDocument,
)


# ─────────────────────────────────────────────────────────────────────────────
# USER tests
# ─────────────────────────────────────────────────────────────────────────────

class TestUserCRUD:
    def test_create_and_fetch_by_email(self, repo: FirebaseResearchRepository):
        user = repo.create_user(email="alice@test.com", name="Alice")
        assert user.id is not None
        assert user.email == "alice@test.com"

        fetched = repo.get_user_by_email("alice@test.com")
        assert fetched is not None
        assert fetched.id == user.id
        assert fetched.name == "Alice"

    def test_create_and_fetch_by_id(self, repo: FirebaseResearchRepository):
        user = repo.create_user(email="bob@test.com")
        fetched = repo.get_user_by_id(user.id)
        assert fetched is not None
        assert fetched.email == "bob@test.com"

    def test_fetch_nonexistent_user_returns_none(self, repo: FirebaseResearchRepository):
        result = repo.get_user_by_id(999999)
        assert result is None

    def test_fetch_by_nonexistent_email_returns_none(self, repo: FirebaseResearchRepository):
        result = repo.get_user_by_email("ghost@test.com")
        assert result is None

    def test_email_lookup_is_case_insensitive(self, repo: FirebaseResearchRepository):
        repo.create_user(email="Carol@Test.COM")
        fetched = repo.get_user_by_email("carol@test.com")
        assert fetched is not None

    def test_update_user_via_save(self, repo: FirebaseResearchRepository):
        user = repo.create_user(email="dan@test.com")
        user.name = "Dan Updated"
        user.is_verified = True
        repo.save(user)
        updated = repo.get_user_by_id(user.id)
        assert updated.name == "Dan Updated"
        assert updated.is_verified is True

    def test_list_users(self, repo: FirebaseResearchRepository):
        repo.create_user(email="u1@test.com")
        repo.create_user(email="u2@test.com")
        users = repo.list_users()
        assert len(users) >= 2

    def test_create_user_with_google_id(self, repo: FirebaseResearchRepository):
        user = repo.create_user(
            email="guser@test.com",
            google_id="google-uid-abc123",
            google_email="guser@test.com",
            profile_pic="https://example.com/pic.jpg",
        )
        fetched = repo.get_user_by_google_id("google-uid-abc123")
        assert fetched is not None
        assert fetched.google_id == "google-uid-abc123"


# ─────────────────────────────────────────────────────────────────────────────
# WORKSPACE tests
# ─────────────────────────────────────────────────────────────────────────────

class TestWorkspaceCRUD:
    def test_create_and_list_workspaces(self, repo: FirebaseResearchRepository):
        user = repo.create_user(email="workuser@test.com")
        ws = repo.create_workspace(user_id=user.id, name="My Workspace", description="Test WS")
        assert ws.id is not None
        assert ws.name == "My Workspace"
        assert ws.user_id == user.id

        listed = repo.list_workspaces_for_user(user.id)
        assert len(listed) == 1
        assert listed[0].id == ws.id

    def test_find_workspace_for_user(self, repo: FirebaseResearchRepository):
        user = repo.create_user(email="wsget@test.com")
        ws = repo.create_workspace(user_id=user.id, name="WS-Get")
        fetched = repo.find_workspace_for_user(ws.id, user.id)
        assert fetched is not None
        assert fetched.name == "WS-Get"

    def test_workspace_isolation_between_users(self, repo: FirebaseResearchRepository):
        u1 = repo.create_user(email="u1@test.com")
        u2 = repo.create_user(email="u2@test.com")
        repo.create_workspace(user_id=u1.id, name="U1 WS")
        repo.create_workspace(user_id=u2.id, name="U2 WS")

        u1_workspaces = repo.list_workspaces_for_user(u1.id)
        u2_workspaces = repo.list_workspaces_for_user(u2.id)

        assert all(ws.user_id == u1.id for ws in u1_workspaces)
        assert all(ws.user_id == u2.id for ws in u2_workspaces)

    def test_delete_workspace(self, repo: FirebaseResearchRepository):
        user = repo.create_user(email="wsdel@test.com")
        ws = repo.create_workspace(user_id=user.id, name="To Delete")
        repo.delete_workspace_graph(ws.id)
        fetched = repo.find_workspace_for_user(ws.id, user.id)
        assert fetched is None

    def test_empty_workspace_list_for_new_user(self, repo: FirebaseResearchRepository):
        user = repo.create_user(email="newuser@test.com")
        workspaces = repo.list_workspaces_for_user(user.id)
        assert workspaces == []

    def test_find_workspace_wrong_user_returns_none(self, repo: FirebaseResearchRepository):
        u1 = repo.create_user(email="owner@test.com")
        u2 = repo.create_user(email="thief@test.com")
        ws = repo.create_workspace(user_id=u1.id, name="Private WS")
        fetched = repo.find_workspace_for_user(ws.id, u2.id)
        assert fetched is None

    def test_get_or_create_default_workspace(self, repo: FirebaseResearchRepository):
        user = repo.create_user(email="defaultws@test.com")
        ws1 = repo.get_or_create_default_workspace(user.id)
        ws2 = repo.get_or_create_default_workspace(user.id)
        assert ws1.id == ws2.id  # idempotent


# ─────────────────────────────────────────────────────────────────────────────
# PAPER tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPaperCRUD:
    def test_add_and_list_papers(self, repo: FirebaseResearchRepository):
        user = repo.create_user(email="paperuser@test.com")
        ws = repo.create_workspace(user_id=user.id, name="Papers WS")

        paper = repo.create_paper(
            workspace_id=ws.id,
            title="Attention Is All You Need",
            authors="Vaswani et al.",
            abstract="A Transformer model...",
            url="https://arxiv.org/abs/1706.03762",
        )
        assert paper.id is not None
        assert paper.title == "Attention Is All You Need"

        papers = repo.list_papers_for_workspace(ws.id)
        assert len(papers) == 1
        assert papers[0].id == paper.id

    def test_find_paper_for_user(self, repo: FirebaseResearchRepository):
        user = repo.create_user(email="findpaper@test.com")
        ws = repo.create_workspace(user_id=user.id, name="FP WS")
        paper = repo.create_paper(
            workspace_id=ws.id,
            title="Found Paper", authors="A", abstract="B",
        )
        found = repo.find_paper_for_user(paper.id, user.id)
        assert found is not None
        assert found.id == paper.id

    def test_papers_isolated_between_workspaces(self, repo: FirebaseResearchRepository):
        user = repo.create_user(email="papisisolate@test.com")
        ws1 = repo.create_workspace(user_id=user.id, name="WS1")
        ws2 = repo.create_workspace(user_id=user.id, name="WS2")
        repo.create_paper(workspace_id=ws1.id, title="Paper in WS1", authors="A", abstract="B")
        ws2_papers = repo.list_papers_for_workspace(ws2.id)
        assert ws2_papers == []


# ─────────────────────────────────────────────────────────────────────────────
# SEARCH HISTORY tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSearchHistory:
    def test_record_and_list_search_history(self, repo: FirebaseResearchRepository):
        user = repo.create_user(email="searcher@test.com")
        repo.record_search_history(
            user_id=user.id,
            query="transformer attention",
            source="arxiv",
            result_count=42,
        )
        history = repo.list_search_history_for_user(user_id=user.id, limit=10)
        assert len(history) == 1
        assert history[0].query == "transformer attention"
        assert history[0].result_count == 42

    def test_search_history_isolated_per_user(self, repo: FirebaseResearchRepository):
        u1 = repo.create_user(email="hist1@test.com")
        u2 = repo.create_user(email="hist2@test.com")
        repo.record_search_history(user_id=u1.id, query="bert", source="semantic_scholar", result_count=5)

        u2_history = repo.list_search_history_for_user(user_id=u2.id, limit=10)
        assert u2_history == []

    def test_delete_all_search_history(self, repo: FirebaseResearchRepository):
        user = repo.create_user(email="delhistory@test.com")
        repo.record_search_history(user_id=user.id, query="gpt4", source="arxiv", result_count=1)
        repo.delete_search_history(user.id)
        history = repo.list_search_history_for_user(user_id=user.id, limit=10)
        assert history == []


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSessionState:
    def test_create_and_get_session_state(self, repo: FirebaseResearchRepository):
        user = repo.create_user(email="session@test.com")
        state = repo.create_session_state(user.id)
        assert state.user_id == user.id
        assert state.page_path == "/home"

        fetched = repo.get_session_state_for_user(user.id)
        assert fetched is not None
        assert fetched.user_id == user.id

    def test_session_state_not_found_returns_none(self, repo: FirebaseResearchRepository):
        state = repo.get_session_state_for_user(user_id=88888)
        assert state is None
