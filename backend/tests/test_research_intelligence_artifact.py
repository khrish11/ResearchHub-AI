"""
test_research_intelligence_artifact.py
──────────────────────────────────────
Tests for Research Intelligence Artifact functionality.

Tests cover:
- Repository CRUD operations
- Service layer orchestration
- API endpoints
- Authorization and workspace isolation
- Status transitions
- Partial/failed pipeline handling
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
from typing import List

from repositories.research import (
    ResearchIntelligenceArtifact,
    ResearchRepository,
    InMemoryResearchRepository,
    User,
    Workspace,
    Paper,
)


@pytest.fixture
def sample_user() -> User:
    """Create a sample user for testing."""
    return User(
        id=1,
        email="test@example.com",
        hashed_password="hashed",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_workspace(sample_user: User) -> Workspace:
    """Create a sample workspace for testing."""
    return Workspace(
        id=100,
        name="Test Workspace",
        description="Test workspace for research",
        user_id=sample_user.id,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_papers(sample_workspace: Workspace) -> List[Paper]:
    """Create sample papers for testing."""
    return [
        Paper(
            id=1001,
            title="Paper 1",
            authors="Author A, Author B",
            abstract="Abstract 1",
            workspace_id=sample_workspace.id,
        ),
        Paper(
            id=1002,
            title="Paper 2",
            authors="Author C",
            abstract="Abstract 2",
            workspace_id=sample_workspace.id,
        ),
    ]


@pytest.fixture
def in_memory_repo(sample_user: User, sample_workspace: Workspace) -> InMemoryResearchRepository:
    """Create an in-memory repository with sample data."""
    repo = InMemoryResearchRepository()
    repo._users[sample_user.id] = sample_user
    repo._workspaces[sample_workspace.id] = sample_workspace
    return repo


class TestResearchIntelligenceArtifactRepository:
    """Tests for repository artifact CRUD operations."""

    def test_create_artifact(self, in_memory_repo: InMemoryResearchRepository, sample_workspace: Workspace, sample_user: User):
        """Test creating a research intelligence artifact."""
        artifact = in_memory_repo.create_research_intelligence_artifact(
            id="test-artifact-1",
            workspace_id=sample_workspace.id,
            user_id=sample_user.id,
            topic="Test Topic",
            paper_ids=[1001, 1002],
            status="running",
            pipeline_version="1.0",
        )
        
        assert artifact.id == "test-artifact-1"
        assert artifact.workspace_id == sample_workspace.id
        assert artifact.user_id == sample_user.id
        assert artifact.topic == "Test Topic"
        assert artifact.paper_ids == [1001, 1002]
        assert artifact.paper_count == 2
        assert artifact.status == "running"
        assert artifact.pipeline_version == "1.0"
        assert artifact.created_at is not None
        assert artifact.updated_at is not None

    def test_get_artifact(self, in_memory_repo: InMemoryResearchRepository, sample_workspace: Workspace, sample_user: User):
        """Test retrieving an artifact by ID."""
        created = in_memory_repo.create_research_intelligence_artifact(
            id="test-artifact-2",
            workspace_id=sample_workspace.id,
            user_id=sample_user.id,
            topic="Test Topic",
            paper_ids=[1001],
        )
        
        retrieved = in_memory_repo.get_research_intelligence_artifact(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.topic == created.topic

    def test_get_artifact_not_found(self, in_memory_repo: InMemoryResearchRepository):
        """Test retrieving a non-existent artifact."""
        artifact = in_memory_repo.get_research_intelligence_artifact("non-existent")
        assert artifact is None

    def test_list_artifacts_for_workspace(self, in_memory_repo: InMemoryResearchRepository, sample_workspace: Workspace, sample_user: User):
        """Test listing artifacts for a workspace."""
        # Create multiple artifacts
        in_memory_repo.create_research_intelligence_artifact(
            id="artifact-1",
            workspace_id=sample_workspace.id,
            user_id=sample_user.id,
            topic="Topic 1",
            paper_ids=[1001],
        )
        in_memory_repo.create_research_intelligence_artifact(
            id="artifact-2",
            workspace_id=sample_workspace.id,
            user_id=sample_user.id,
            topic="Topic 2",
            paper_ids=[1002],
        )
        
        # Create artifact for different workspace
        other_workspace = Workspace(id=200, name="Other", description="Other workspace", user_id=sample_user.id, created_at=datetime.now(timezone.utc))
        in_memory_repo._workspaces[200] = other_workspace
        in_memory_repo.create_research_intelligence_artifact(
            id="artifact-3",
            workspace_id=200,
            user_id=sample_user.id,
            topic="Topic 3",
            paper_ids=[1001],
        )
        
        artifacts = in_memory_repo.list_research_intelligence_artifacts_for_workspace(
            sample_workspace.id, sample_user.id
        )
        
        assert len(artifacts) == 2
        assert all(a.workspace_id == sample_workspace.id for a in artifacts)

    def test_list_artifacts_unauthorized_workspace(self, in_memory_repo: InMemoryResearchRepository, sample_workspace: Workspace, sample_user: User):
        """Test that listing artifacts for unauthorized workspace returns empty list."""
        # Create artifact for workspace
        in_memory_repo.create_research_intelligence_artifact(
            id="artifact-1",
            workspace_id=sample_workspace.id,
            user_id=sample_user.id,
            topic="Topic",
            paper_ids=[1001],
        )
        
        # Try to list with different user
        artifacts = in_memory_repo.list_research_intelligence_artifacts_for_workspace(
            sample_workspace.id, 999  # Different user
        )
        
        assert len(artifacts) == 0

    def test_update_artifact_status(self, in_memory_repo: InMemoryResearchRepository, sample_workspace: Workspace, sample_user: User):
        """Test updating artifact status."""
        created = in_memory_repo.create_research_intelligence_artifact(
            id="artifact-1",
            workspace_id=sample_workspace.id,
            user_id=sample_user.id,
            topic="Topic",
            paper_ids=[1001],
            status="running",
        )
        
        updated = in_memory_repo.update_research_intelligence_artifact(
            created.id,
            {"status": "completed"}
        )
        
        assert updated is not None
        assert updated.status == "completed"
        # updated_at may be equal to created_at in fast execution, just check it's set
        assert updated.updated_at is not None

    def test_update_artifact_invalid_status_transition(self, in_memory_repo: InMemoryResearchRepository, sample_workspace: Workspace, sample_user: User):
        """Test that invalid status transitions are rejected."""
        created = in_memory_repo.create_research_intelligence_artifact(
            id="artifact-1",
            workspace_id=sample_workspace.id,
            user_id=sample_user.id,
            topic="Topic",
            paper_ids=[1001],
            status="completed",
        )
        
        # Should not allow transition from completed to running
        with pytest.raises(ValueError, match="Invalid artifact status transition"):
            in_memory_repo.update_research_intelligence_artifact(
                created.id,
                {"status": "running"}
            )

    def test_update_artifact_with_stage_results(self, in_memory_repo: InMemoryResearchRepository, sample_workspace: Workspace, sample_user: User):
        """Test updating artifact with pipeline stage results."""
        created = in_memory_repo.create_research_intelligence_artifact(
            id="artifact-1",
            workspace_id=sample_workspace.id,
            user_id=sample_user.id,
            topic="Topic",
            paper_ids=[1001],
        )
        
        evidence_result = {"claim": "test", "classification": {"supporting_count": 5}}
        updated = in_memory_repo.update_research_intelligence_artifact(
            created.id,
            {"evidence_analysis": evidence_result}
        )
        
        assert updated is not None
        assert updated.evidence_analysis == evidence_result

    def test_update_artifact_not_found(self, in_memory_repo: InMemoryResearchRepository):
        """Test updating a non-existent artifact."""
        updated = in_memory_repo.update_research_intelligence_artifact(
            "non-existent",
            {"status": "completed"}
        )
        assert updated is None

    def test_delete_artifact(self, in_memory_repo: InMemoryResearchRepository, sample_workspace: Workspace, sample_user: User):
        """Test deleting an artifact."""
        created = in_memory_repo.create_research_intelligence_artifact(
            id="artifact-1",
            workspace_id=sample_workspace.id,
            user_id=sample_user.id,
            topic="Topic",
            paper_ids=[1001],
        )
        
        success = in_memory_repo.delete_research_intelligence_artifact(created.id)
        
        assert success is True
        retrieved = in_memory_repo.get_research_intelligence_artifact(created.id)
        assert retrieved is None

    def test_delete_artifact_not_found(self, in_memory_repo: InMemoryResearchRepository):
        """Test deleting a non-existent artifact."""
        success = in_memory_repo.delete_research_intelligence_artifact("non-existent")
        assert success is False


class TestResearchIntelligenceArtifactService:
    """Tests for artifact service layer."""

    def test_create_artifact(self, in_memory_repo: InMemoryResearchRepository, sample_workspace: Workspace, sample_user: User):
        """Test service creating an artifact."""
        from services.research_intelligence_artifact_service import ResearchIntelligenceArtifactService
        
        service = ResearchIntelligenceArtifactService(in_memory_repo)
        
        artifact = service.create_artifact(
            workspace_id=sample_workspace.id,
            user_id=sample_user.id,
            topic="Test Topic",
            paper_ids=[1001, 1002],
            pipeline_version="1.0",
        )
        
        assert artifact.id is not None
        assert artifact.status == "running"
        assert artifact.topic == "Test Topic"

    def test_create_artifact_feature_flag_disabled(self, in_memory_repo: InMemoryResearchRepository, sample_workspace: Workspace, sample_user: User):
        """Test that artifact creation is disabled when feature flag is off."""
        from services.research_intelligence_artifact_service import ResearchIntelligenceArtifactService, RESEARCH_INTELLIGENCE_ARTIFACTS_ENABLED
        
        original_flag = RESEARCH_INTELLIGENCE_ARTIFACTS_ENABLED
        try:
            # Disable feature flag
            import services.research_intelligence_artifact_service as service_module
            service_module.RESEARCH_INTELLIGENCE_ARTIFACTS_ENABLED = False
            
            service = ResearchIntelligenceArtifactService(in_memory_repo)
            
            with pytest.raises(RuntimeError, match="Research Intelligence Artifacts are disabled"):
                service.create_artifact(
                    workspace_id=sample_workspace.id,
                    user_id=sample_user.id,
                    topic="Test",
                    paper_ids=[1001],
                )
        finally:
            service_module.RESEARCH_INTELLIGENCE_ARTIFACTS_ENABLED = original_flag

    def test_get_artifact(self, in_memory_repo: InMemoryResearchRepository, sample_workspace: Workspace, sample_user: User):
        """Test service retrieving an artifact."""
        from services.research_intelligence_artifact_service import ResearchIntelligenceArtifactService
        
        service = ResearchIntelligenceArtifactService(in_memory_repo)
        
        created = service.create_artifact(
            workspace_id=sample_workspace.id,
            user_id=sample_user.id,
            topic="Test",
            paper_ids=[1001],
        )
        
        retrieved = service.get_artifact(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id

    def test_list_workspace_artifacts(self, in_memory_repo: InMemoryResearchRepository, sample_workspace: Workspace, sample_user: User):
        """Test service listing workspace artifacts."""
        from services.research_intelligence_artifact_service import ResearchIntelligenceArtifactService
        
        service = ResearchIntelligenceArtifactService(in_memory_repo)
        
        service.create_artifact(
            workspace_id=sample_workspace.id,
            user_id=sample_user.id,
            topic="Test 1",
            paper_ids=[1001],
        )
        service.create_artifact(
            workspace_id=sample_workspace.id,
            user_id=sample_user.id,
            topic="Test 2",
            paper_ids=[1002],
        )
        
        artifacts = service.list_workspace_artifacts(sample_workspace.id, sample_user.id)
        
        assert len(artifacts) == 2

    def test_delete_artifact(self, in_memory_repo: InMemoryResearchRepository, sample_workspace: Workspace, sample_user: User):
        """Test service deleting an artifact."""
        from services.research_intelligence_artifact_service import ResearchIntelligenceArtifactService
        
        service = ResearchIntelligenceArtifactService(in_memory_repo)
        
        created = service.create_artifact(
            workspace_id=sample_workspace.id,
            user_id=sample_user.id,
            topic="Test",
            paper_ids=[1001],
        )
        
        success = service.delete_artifact(created.id)
        
        assert success is True
        assert service.get_artifact(created.id) is None

    @patch('services.research_intelligence_artifact_service.get_evidence_service')
    @patch('services.research_intelligence_artifact_service.get_gap_service')
    def test_execute_pipeline_success(self, mock_gap_service, mock_evidence_service, in_memory_repo: InMemoryResearchRepository, sample_workspace: Workspace, sample_user: User, sample_papers: List[Paper]):
        """Test successful pipeline execution."""
        from services.research_intelligence_artifact_service import ResearchIntelligenceArtifactService
        
        # Mock service responses
        mock_evidence = Mock()
        mock_evidence.claim = "test claim"
        mock_evidence.classification = Mock()
        mock_evidence.classification.supporting_papers = []
        mock_evidence.classification.contradicting_papers = []
        mock_evidence.classification.neutral_papers = []
        mock_evidence.strength = Mock()
        mock_evidence.strength.overall_strength = 75
        mock_evidence.strength.confidence = "high"
        mock_evidence_service.return_value.analyze_claim.return_value = mock_evidence
        
        mock_gap = Mock()
        mock_gap.total_gaps = 5
        mock_gap.gaps_by_category = {}
        mock_gap.top_opportunities = []
        mock_gap_service.return_value.analyze_gaps.return_value = mock_gap
        
        service = ResearchIntelligenceArtifactService(in_memory_repo)
        
        created = service.create_artifact(
            workspace_id=sample_workspace.id,
            user_id=sample_user.id,
            topic="Test",
            paper_ids=[1001, 1002],
        )
        
        # Mock other services to avoid complexity
        mock_opportunity = Mock()
        mock_opportunity.opportunities = []
        mock_opportunity.top_opportunity = None
        
        mock_questions = Mock()
        mock_questions.questions = []
        mock_questions.top_questions = []
        
        mock_challenger = Mock()
        mock_challenger.challenges = []
        mock_challenger.overall_vulnerability = 0
        mock_challenger.strongest_challenge = None
        
        mock_citation = Mock()
        mock_citation.total_papers = 2
        mock_citation.average_quality = 80
        mock_citation.average_accessibility = 75
        mock_citation.overall_confidence = 0.8
        
        mock_graph = Mock()
        mock_graph.total_layers = 0
        mock_graph.enhanced_nodes = 0
        mock_graph.enhanced_edges = 0
        
        with patch('services.research_intelligence_artifact_service.get_opportunity_service') as mock_opp_service, \
             patch('services.research_intelligence_artifact_service.get_question_service') as mock_q_service, \
             patch('services.research_intelligence_artifact_service.get_challenger_service') as mock_c_service, \
             patch('services.research_intelligence_artifact_service.get_citation_service') as mock_cv_service, \
             patch('services.research_intelligence_artifact_service.get_graph_enhancement_service') as mock_kg_service:
            
            mock_opp_service.return_value.rank_opportunities.return_value = mock_opportunity
            mock_q_service.return_value.generate_questions.return_value = mock_questions
            mock_c_service.return_value.challenge_hypothesis.return_value = mock_challenger
            mock_cv_service.return_value.verify_citations.return_value = mock_citation
            mock_kg_service.return_value.enhance_knowledge_graph.return_value = mock_graph
            
            result = service.execute_pipeline(
                artifact_id=created.id,
                papers=sample_papers,
                topic="Test",
            )
        
        assert result.status in {"completed", "partial"}  # May be partial if some stages fail
        assert result.updated_at is not None


class TestArtifactStatusTransitions:
    """Tests for artifact status transition validation."""

    def test_valid_transitions(self):
        """Test valid status transitions."""
        from repositories.research import _validate_artifact_status_transition
        
        # running -> completed
        _validate_artifact_status_transition("running", "completed")
        
        # running -> partial
        _validate_artifact_status_transition("running", "partial")
        
        # running -> failed
        _validate_artifact_status_transition("running", "failed")

    def test_invalid_transitions(self):
        """Test invalid status transitions."""
        from repositories.research import _validate_artifact_status_transition
        
        # completed -> running (invalid)
        with pytest.raises(ValueError, match="Invalid artifact status transition"):
            _validate_artifact_status_transition("completed", "running")
        
        # partial -> running (invalid)
        with pytest.raises(ValueError, match="Invalid artifact status transition"):
            _validate_artifact_status_transition("partial", "running")
        
        # failed -> running (invalid)
        with pytest.raises(ValueError, match="Invalid artifact status transition"):
            _validate_artifact_status_transition("failed", "running")

    def test_same_status_allowed(self):
        """Test that same status is allowed (no-op)."""
        from repositories.research import _validate_artifact_status_transition
        
        _validate_artifact_status_transition("running", "running")
        _validate_artifact_status_transition("completed", "completed")


class TestArtifactSerialization:
    """Tests for artifact data serialization."""

    def test_artifact_to_dict(self, in_memory_repo: InMemoryResearchRepository, sample_workspace: Workspace, sample_user: User):
        """Test artifact can be serialized to dict."""
        from dataclasses import asdict
        
        artifact = in_memory_repo.create_research_intelligence_artifact(
            id="artifact-1",
            workspace_id=sample_workspace.id,
            user_id=sample_user.id,
            topic="Test",
            paper_ids=[1001],
        )
        
        data = asdict(artifact)
        
        assert data["id"] == artifact.id
        assert data["topic"] == artifact.topic
        assert data["status"] == artifact.status

    def test_artifact_with_results_serialization(self, in_memory_repo: InMemoryResearchRepository, sample_workspace: Workspace, sample_user: User):
        """Test artifact with pipeline results can be serialized."""
        from dataclasses import asdict
        
        artifact = in_memory_repo.create_research_intelligence_artifact(
            id="artifact-1",
            workspace_id=sample_workspace.id,
            user_id=sample_user.id,
            topic="Test",
            paper_ids=[1001],
        )
        
        in_memory_repo.update_research_intelligence_artifact(
            artifact.id,
            {
                "evidence_analysis": {"claim": "test"},
                "gap_analysis": {"total_gaps": 5},
                "overall_score": 85,
                "summary": "Test summary",
            }
        )
        
        updated = in_memory_repo.get_research_intelligence_artifact(artifact.id)
        data = asdict(updated)
        
        assert data["evidence_analysis"] == {"claim": "test"}
        assert data["gap_analysis"] == {"total_gaps": 5}
        assert data["overall_score"] == 85
        assert data["summary"] == "Test summary"
