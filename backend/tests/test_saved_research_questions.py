"""
tests/test_saved_research_questions.py — Unit tests for SavedResearchQuestion CRUD operations.

Tests cover:
- FirebaseResearchRepository implementation
- InMemoryResearchRepository implementation
- Authorization and workspace ownership
- Edge cases and error handling
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from repositories.research import (
    FirebaseResearchRepository,
    InMemoryResearchRepository,
    SavedResearchQuestion,
    User,
    Workspace,
)


class TestSavedResearchQuestionFirebase:
    """Test FirebaseResearchRepository saved research question operations."""

    def test_create_and_fetch_question(self, repo: FirebaseResearchRepository):
        """Test creating and retrieving a saved research question."""
        user = repo.create_user(email="testuser@test.com")
        workspace = repo.create_workspace(user_id=user.id, name="Test Workspace")
        
        question = repo.create_saved_research_question(
            id="rq_test_001",
            workspace_id=workspace.id,
            user_id=user.id,
            question="What is the effect of X on Y?",
            category="exploratory",
            complexity="moderate",
            confidence=75,
            novelty=80,
            feasibility=70,
            impact=85,
            source_gap_id="gap_001",
            source_gap_description="Gap in understanding X",
            supporting_papers=[1, 2, 3],
            rationale="This question addresses a critical gap",
            source_artifact_id="artifact_001",
        )
        
        assert question.id == "rq_test_001"
        assert question.workspace_id == workspace.id
        assert question.user_id == user.id
        assert question.question == "What is the effect of X on Y?"
        assert question.category == "exploratory"
        assert question.complexity == "moderate"
        assert question.confidence == 75
        assert question.novelty == 80
        assert question.feasibility == 70
        assert question.impact == 85
        assert question.source_gap_id == "gap_001"
        assert question.supporting_papers == [1, 2, 3]
        
        fetched = repo.get_saved_research_question("rq_test_001")
        assert fetched is not None
        assert fetched.id == question.id
        assert fetched.question == question.question

    def test_list_questions_for_workspace(self, repo: FirebaseResearchRepository):
        """Test listing saved questions for a workspace."""
        user = repo.create_user(email="listuser@test.com")
        workspace = repo.create_workspace(user_id=user.id, name="List Test WS")
        
        repo.create_saved_research_question(
            id="rq_list_001",
            workspace_id=workspace.id,
            user_id=user.id,
            question="Question 1",
            category="exploratory",
            complexity="simple",
            confidence=60,
            novelty=70,
            feasibility=80,
            impact=75,
        )
        repo.create_saved_research_question(
            id="rq_list_002",
            workspace_id=workspace.id,
            user_id=user.id,
            question="Question 2",
            category="confirmatory",
            complexity="moderate",
            confidence=80,
            novelty=65,
            feasibility=75,
            impact=85,
        )
        
        questions = repo.list_saved_research_questions_for_workspace(workspace.id, user.id)
        assert len(questions) == 2
        assert all(q.workspace_id == workspace.id for q in questions)

    def test_delete_question(self, repo: FirebaseResearchRepository):
        """Test deleting a saved research question."""
        user = repo.create_user(email="deleteuser@test.com")
        workspace = repo.create_workspace(user_id=user.id, name="Delete Test WS")
        
        question = repo.create_saved_research_question(
            id="rq_delete_001",
            workspace_id=workspace.id,
            user_id=user.id,
            question="To be deleted",
            category="exploratory",
            complexity="simple",
            confidence=60,
            novelty=70,
            feasibility=80,
            impact=75,
        )
        
        # Verify it exists
        assert repo.get_saved_research_question("rq_delete_001") is not None
        
        # Delete it
        success = repo.delete_saved_research_question("rq_delete_001")
        assert success is True
        
        # Verify it's gone
        assert repo.get_saved_research_question("rq_delete_001") is None

    def test_delete_nonexistent_question_returns_false(self, repo: FirebaseResearchRepository):
        """Test deleting a non-existent question returns False."""
        success = repo.delete_saved_research_question("rq_nonexistent")
        assert success is False

    def test_list_questions_respects_workspace_ownership(self, repo: FirebaseResearchRepository):
        """Test that listing questions respects workspace ownership."""
        user_a = repo.create_user(email="usera@test.com")
        user_b = repo.create_user(email="userb@test.com")
        workspace_a = repo.create_workspace(user_id=user_a.id, name="Workspace A")
        workspace_b = repo.create_workspace(user_id=user_b.id, name="Workspace B")
        
        # Create question in workspace A
        repo.create_saved_research_question(
            id="rq_auth_001",
            workspace_id=workspace_a.id,
            user_id=user_a.id,
            question="User A's question",
            category="exploratory",
            complexity="simple",
            confidence=60,
            novelty=70,
            feasibility=80,
            impact=75,
        )
        
        # User B should not see User A's questions
        questions_b = repo.list_saved_research_questions_for_workspace(workspace_a.id, user_b.id)
        assert len(questions_b) == 0
        
        # User A should see their own questions
        questions_a = repo.list_saved_research_questions_for_workspace(workspace_a.id, user_a.id)
        assert len(questions_a) == 1

    def test_confidence_clamping(self, repo: FirebaseResearchRepository):
        """Test that confidence scores are clamped to 0-100 range."""
        user = repo.create_user(email="clampuser@test.com")
        workspace = repo.create_workspace(user_id=user.id, name="Clamp Test WS")
        
        # Test values outside valid range
        question = repo.create_saved_research_question(
            id="rq_clamp_001",
            workspace_id=workspace.id,
            user_id=user.id,
            question="Test question",
            category="exploratory",
            complexity="simple",
            confidence=150,  # Should be clamped to 100
            novelty=-50,   # Should be clamped to 0
            feasibility=200,  # Should be clamped to 100
            impact=-10,    # Should be clamped to 0
        )
        
        assert question.confidence == 100
        assert question.novelty == 0
        assert question.feasibility == 100
        assert question.impact == 0

    def test_optional_fields_default_to_none(self, repo: FirebaseResearchRepository):
        """Test that optional fields default to None when not provided."""
        user = repo.create_user(email="optionaluser@test.com")
        workspace = repo.create_workspace(user_id=user.id, name="Optional Test WS")
        
        question = repo.create_saved_research_question(
            id="rq_optional_001",
            workspace_id=workspace.id,
            user_id=user.id,
            question="Minimal question",
            category="exploratory",
            complexity="simple",
            confidence=60,
            novelty=70,
            feasibility=80,
            impact=75,
            # Optional fields omitted
        )
        
        assert question.source_gap_id is None
        assert question.source_gap_description is None
        assert question.supporting_papers == []
        assert question.rationale is None
        assert question.source_artifact_id is None

    def test_supporting_papers_conversion(self, repo: FirebaseResearchRepository):
        """Test that supporting papers are correctly converted to integers."""
        user = repo.create_user(email="papersuser@test.com")
        workspace = repo.create_workspace(user_id=user.id, name="Papers Test WS")
        
        question = repo.create_saved_research_question(
            id="rq_papers_001",
            workspace_id=workspace.id,
            user_id=user.id,
            question="Test question",
            category="exploratory",
            complexity="simple",
            confidence=60,
            novelty=70,
            feasibility=80,
            impact=75,
            supporting_papers=["1", "2", "3"],  # Strings should be converted to ints
        )
        
        assert question.supporting_papers == [1, 2, 3]
        assert all(isinstance(p, int) for p in question.supporting_papers)


class TestSavedResearchQuestionInMemory:
    """Test InMemoryResearchRepository saved research question operations."""

    def test_create_and_fetch_question(self):
        """Test creating and retrieving a saved research question in memory."""
        repo = InMemoryResearchRepository()
        user = repo.create_user(email="testuser@test.com")
        workspace = repo.create_workspace(user_id=user.id, name="Test Workspace")
        
        question = repo.create_saved_research_question(
            id="rq_mem_001",
            workspace_id=workspace.id,
            user_id=user.id,
            question="What is the effect of X on Y?",
            category="exploratory",
            complexity="moderate",
            confidence=75,
            novelty=80,
            feasibility=70,
            impact=85,
        )
        
        assert question.id == "rq_mem_001"
        assert question.workspace_id == workspace.id
        
        fetched = repo.get_saved_research_question("rq_mem_001")
        assert fetched is not None
        assert fetched.id == question.id

    def test_list_questions_for_workspace(self):
        """Test listing saved questions for a workspace in memory."""
        repo = InMemoryResearchRepository()
        user = repo.create_user(email="listuser@test.com")
        workspace = repo.create_workspace(user_id=user.id, name="List Test WS")
        
        repo.create_saved_research_question(
            id="rq_mem_list_001",
            workspace_id=workspace.id,
            user_id=user.id,
            question="Question 1",
            category="exploratory",
            complexity="simple",
            confidence=60,
            novelty=70,
            feasibility=80,
            impact=75,
        )
        repo.create_saved_research_question(
            id="rq_mem_list_002",
            workspace_id=workspace.id,
            user_id=user.id,
            question="Question 2",
            category="confirmatory",
            complexity="moderate",
            confidence=80,
            novelty=65,
            feasibility=75,
            impact=85,
        )
        
        questions = repo.list_saved_research_questions_for_workspace(workspace.id, user.id)
        assert len(questions) == 2

    def test_delete_question(self):
        """Test deleting a saved research question in memory."""
        repo = InMemoryResearchRepository()
        user = repo.create_user(email="deleteuser@test.com")
        workspace = repo.create_workspace(user_id=user.id, name="Delete Test WS")
        
        repo.create_saved_research_question(
            id="rq_mem_delete_001",
            workspace_id=workspace.id,
            user_id=user.id,
            question="To be deleted",
            category="exploratory",
            complexity="simple",
            confidence=60,
            novelty=70,
            feasibility=80,
            impact=75,
        )
        
        success = repo.delete_saved_research_question("rq_mem_delete_001")
        assert success is True
        
        assert repo.get_saved_research_question("rq_mem_delete_001") is None

    def test_workspace_ownership_verification(self):
        """Test that workspace ownership is verified in memory."""
        repo = InMemoryResearchRepository()
        user_a = repo.create_user(email="usera@test.com")
        user_b = repo.create_user(email="userb@test.com")
        workspace_a = repo.create_workspace(user_id=user_a.id, name="Workspace A")
        
        repo.create_saved_research_question(
            id="rq_mem_auth_001",
            workspace_id=workspace_a.id,
            user_id=user_a.id,
            question="User A's question",
            category="exploratory",
            complexity="simple",
            confidence=60,
            novelty=70,
            feasibility=80,
            impact=75,
        )
        
        # User B should not see User A's questions
        questions_b = repo.list_saved_research_questions_for_workspace(workspace_a.id, user_b.id)
        assert len(questions_b) == 0
        
        # User A should see their own questions
        questions_a = repo.list_saved_research_questions_for_workspace(workspace_a.id, user_a.id)
        assert len(questions_a) == 1

    def test_confidence_clamping(self):
        """Test that confidence scores are clamped to 0-100 range in memory."""
        repo = InMemoryResearchRepository()
        user = repo.create_user(email="clampuser@test.com")
        workspace = repo.create_workspace(user_id=user.id, name="Clamp Test WS")
        
        question = repo.create_saved_research_question(
            id="rq_mem_clamp_001",
            workspace_id=workspace.id,
            user_id=user.id,
            question="Test question",
            category="exploratory",
            complexity="simple",
            confidence=150,
            novelty=-50,
            feasibility=200,
            impact=-10,
        )
        
        assert question.confidence == 100
        assert question.novelty == 0
        assert question.feasibility == 100
        assert question.impact == 0


class TestSavedResearchQuestionEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_question_text(self, repo: FirebaseResearchRepository):
        """Test handling of empty question text."""
        user = repo.create_user(email="emptyuser@test.com")
        workspace = repo.create_workspace(user_id=user.id, name="Empty Test WS")
        
        # Empty string should be allowed (validation should happen at API layer)
        question = repo.create_saved_research_question(
            id="rq_empty_001",
            workspace_id=workspace.id,
            user_id=user.id,
            question="",  # Empty question
            category="exploratory",
            complexity="simple",
            confidence=60,
            novelty=70,
            feasibility=80,
            impact=75,
        )
        
        assert question.question == ""

    def test_invalid_workspace_id(self, repo: FirebaseResearchRepository):
        """Test handling of invalid workspace ID."""
        user = repo.create_user(email="invaliduser@test.com")
        
        # Should not raise error, but question won't be accessible
        question = repo.create_saved_research_question(
            id="rq_invalid_001",
            workspace_id=999999,  # Non-existent workspace
            user_id=user.id,
            question="Test question",
            category="exploratory",
            complexity="simple",
            confidence=60,
            novelty=70,
            feasibility=80,
            impact=75,
        )
        
        # Question should be created but not accessible via workspace listing
        questions = repo.list_saved_research_questions_for_workspace(999999, user.id)
        assert len(questions) == 0

    def test_duplicate_question_ids(self, repo: FirebaseResearchRepository):
        """Test handling of duplicate question IDs (should overwrite)."""
        user = repo.create_user(email="dupuser@test.com")
        workspace = repo.create_workspace(user_id=user.id, name="Dup Test WS")
        
        # Create first question
        repo.create_saved_research_question(
            id="rq_dup_001",
            workspace_id=workspace.id,
            user_id=user.id,
            question="First version",
            category="exploratory",
            complexity="simple",
            confidence=60,
            novelty=70,
            feasibility=80,
            impact=75,
        )
        
        # Create second question with same ID (should overwrite)
        repo.create_saved_research_question(
            id="rq_dup_001",
            workspace_id=workspace.id,
            user_id=user.id,
            question="Second version",
            category="confirmatory",
            complexity="moderate",
            confidence=80,
            novelty=85,
            feasibility=75,
            impact=90,
        )
        
        # Should have the second version
        question = repo.get_saved_research_question("rq_dup_001")
        assert question.question == "Second version"
        assert question.category == "confirmatory"
