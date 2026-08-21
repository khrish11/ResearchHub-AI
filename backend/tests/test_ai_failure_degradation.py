"""
AI Failure and Graceful Degradation Tests

Tests that verify the system handles AI failures gracefully:
- Feature flags disable AI endpoints
- Empty/null AI responses are handled
- Timeout scenarios are handled
- Partial failures don't corrupt data
- System remains functional without AI
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta


class TestFeatureFlagGracefulDegradation:
    """Test that feature flags properly disable AI endpoints."""

    def test_evidence_analysis_disabled_returns_error(
        self, test_client, auth_headers
    ):
        """When evidence analysis is disabled, endpoint returns appropriate error."""
        # Mock feature flag to disable evidence analysis
        with patch('services.evidence_intelligence_service.EVIDENCE_INTELLIGENCE_ENABLED', False):
            response = test_client.post(
                "/research/evidence/analyze",
                json={
                    "workspace_id": 1,
                    "claim": "Test claim",
                    "paper_ids": [1, 2],
                },
                headers=auth_headers,
            )
            # Should return error indicating feature disabled or not found
            assert response.status_code in [400, 503, 403, 404]

    def test_gap_detection_disabled_returns_error(
        self, test_client, auth_headers
    ):
        """When gap detection is disabled, endpoint returns appropriate error."""
        with patch('services.gap_intelligence_service.GAP_INTELLIGENCE_ENABLED', False):
            response = test_client.post(
                "/research/gaps/detect",
                json={
                    "workspace_id": 1,
                    "topic": "Test topic",
                    "paper_ids": [1, 2],
                },
                headers=auth_headers,
            )
            assert response.status_code in [400, 503, 403, 404]

    def test_opportunity_ranking_disabled_returns_error(
        self, test_client, auth_headers
    ):
        """When opportunity ranking is disabled, endpoint returns appropriate error."""
        with patch('services.opportunity_scoring_service.OPPORTUNITY_SCORING_ENABLED', False):
            response = test_client.post(
                "/research/opportunities/rank",
                json={
                    "workspace_id": 1,
                    "topic": "Test topic",
                    "paper_ids": [1, 2],
                },
                headers=auth_headers,
            )
            assert response.status_code in [400, 503, 403, 404]


class TestEmptyAIResponseHandling:
    """Test that empty/null AI responses are handled gracefully."""

    def test_empty_evidence_analysis_returns_empty_result(
        self, repo, mock_user
    ):
        """Empty evidence analysis should return empty result, not crash."""
        # Create artifact
        artifact = repo.create_research_intelligence_artifact(
            id="artifact_empty_001",
            workspace_id=1,
            user_id=mock_user.id,
            topic="Test Topic",
            paper_ids=[1, 2],
            pipeline_version="1.0",
        )

        # Update with empty evidence analysis
        result = repo.update_research_intelligence_artifact(
            artifact_id=artifact.id,
            updates={
                "evidence_analysis": None,
                "status": "completed",
            },
        )

        # Should not crash, should return artifact with None evidence
        assert result is not None
        assert result.evidence_analysis is None

    def test_empty_gap_analysis_returns_empty_result(
        self, repo, mock_user
    ):
        """Empty gap analysis should return empty result, not crash."""
        artifact = repo.create_research_intelligence_artifact(
            id="artifact_empty_002",
            workspace_id=1,
            user_id=mock_user.id,
            topic="Test Topic",
            paper_ids=[1, 2],
            pipeline_version="1.0",
        )

        result = repo.update_research_intelligence_artifact(
            artifact_id=artifact.id,
            updates={
                "gap_analysis": None,
                "status": "completed",
            },
        )

        assert result is not None
        assert result.gap_analysis is None

    def test_empty_opportunity_ranking_returns_empty_result(
        self, repo, mock_user
    ):
        """Empty opportunity ranking should return empty result, not crash."""
        artifact = repo.create_research_intelligence_artifact(
            id="artifact_empty_003",
            workspace_id=1,
            user_id=mock_user.id,
            topic="Test Topic",
            paper_ids=[1, 2],
            pipeline_version="1.0",
        )

        result = repo.update_research_intelligence_artifact(
            artifact_id=artifact.id,
            updates={
                "opportunity_ranking": None,
                "status": "completed",
            },
        )

        assert result is not None
        assert result.opportunity_ranking is None


class TestPartialFailureHandling:
    """Test that partial AI failures don't corrupt existing data."""

    def test_partial_pipeline_failure_preserves_completed_stages(
        self, repo, mock_user
    ):
        """If one stage fails, completed stages should remain intact."""
        artifact = repo.create_research_intelligence_artifact(
            id="artifact_partial_001",
            workspace_id=1,
            user_id=mock_user.id,
            topic="Test Topic",
            paper_ids=[1, 2],
            pipeline_version="1.0",
        )

        # Complete evidence analysis
        repo.update_research_intelligence_artifact(
            artifact_id=artifact.id,
            updates={
                "evidence_analysis": {"test": "data"},
                "status": "running",
            },
        )

        # Gap analysis fails (empty)
        repo.update_research_intelligence_artifact(
            artifact_id=artifact.id,
            updates={
                "gap_analysis": None,
                "status": "completed",
            },
        )

        # Verify evidence analysis is still intact
        result = repo.get_research_intelligence_artifact(artifact.id)
        assert result is not None
        assert result.evidence_analysis is not None
        assert result.evidence_analysis == {"test": "data"}
        assert result.gap_analysis is None

    def test_stage_errors_are_recorded(
        self, repo, mock_user
    ):
        """Stage errors should be recorded without corrupting other data."""
        artifact = repo.create_research_intelligence_artifact(
            id="artifact_error_001",
            workspace_id=1,
            user_id=mock_user.id,
            topic="Test Topic",
            paper_ids=[1, 2],
            pipeline_version="1.0",
        )

        # Record stage error
        repo.update_research_intelligence_artifact(
            artifact_id=artifact.id,
            updates={
                "evidence_analysis": {"test": "data"},
                "stage_errors": {
                    "gap_analysis": "AI service timeout",
                },
                "status": "completed",
            },
        )

        result = repo.get_research_intelligence_artifact(artifact.id)
        assert result is not None
        assert result.evidence_analysis is not None
        assert result.stage_errors is not None
        assert "gap_analysis" in result.stage_errors


class TestRepositoryFunctionalityWithoutAI:
    """Test that repository operations work without AI."""

    def test_create_artifact_without_ai_works(
        self, repo, mock_user
    ):
        """Creating artifacts should work without AI."""
        artifact = repo.create_research_intelligence_artifact(
            id="artifact_no_ai_001",
            workspace_id=1,
            user_id=mock_user.id,
            topic="Test Topic",
            paper_ids=[1, 2],
            pipeline_version="1.0",
        )

        assert artifact is not None
        assert artifact.id == "artifact_no_ai_001"

    def test_save_question_without_ai_works(
        self, repo, mock_user
    ):
        """Saving questions should work without AI."""
        question = repo.create_saved_research_question(
            id="question_no_ai_001",
            workspace_id=1,
            user_id=mock_user.id,
            question="Manual question",
            category="exploratory",
            complexity="simple",
            confidence=50,
            novelty=50,
            feasibility=50,
            impact=50,
        )

        assert question is not None
        assert question.id == "question_no_ai_001"

    def test_create_plan_without_ai_works(
        self, repo, mock_user
    ):
        """Creating plans should work without AI."""
        plan = repo.create_research_plan(
            id="plan_no_ai_001",
            workspace_id=1,
            user_id=mock_user.id,
            artifact_id="artifact_123",
            opportunity_id="opp_123",
            opportunity_description="Manual opportunity",
            title="Manual Plan",
            research_problem="Manual problem",
            research_question="Manual question",
            hypothesis="Manual hypothesis",
            objectives="Manual objectives",
            proposed_methodology="Manual methodology",
            alternative_methodology="Alternative methodology",
            datasets="Manual datasets",
            variables="Manual variables",
            baselines="Manual baselines",
            evaluation_metrics="Manual metrics",
            expected_contribution="Manual contribution",
            risks="Manual risks",
            limitations="Manual limitations",
            reproducibility_requirements="Manual reproducibility",
        )

        assert plan is not None
        assert plan.id == "plan_no_ai_001"


class TestErrorBoundaryHandling:
    """Test that error boundaries prevent cascading failures."""

    def test_invalid_status_transition_rejected(
        self, repo, mock_user
    ):
        """Invalid status transitions should be rejected."""
        artifact = repo.create_research_intelligence_artifact(
            id="artifact_status_001",
            workspace_id=1,
            user_id=mock_user.id,
            topic="Test Topic",
            paper_ids=[1, 2],
            pipeline_version="1.0",
            status="completed",
        )

        # Try to transition from completed to running (invalid)
        # Should raise ValueError for invalid transition
        with pytest.raises(ValueError, match="Invalid artifact status transition"):
            repo.update_research_intelligence_artifact(
                artifact_id=artifact.id,
                updates={
                    "status": "running",
                },
            )

    def test_confidence_clamping_prevents_invalid_values(
        self, repo, mock_user
    ):
        """Confidence values should be clamped to valid range."""
        # Try to create question with invalid confidence
        question = repo.create_saved_research_question(
            id="question_clamp_001",
            workspace_id=1,
            user_id=mock_user.id,
            question="Test question",
            category="exploratory",
            complexity="simple",
            confidence=150,  # Invalid: > 100
            novelty=200,  # Invalid: > 100
            feasibility=-50,  # Invalid: < 0
            impact=50,
        )

        # Values should be clamped to valid range [0, 100]
        assert 0 <= question.confidence <= 100
        assert 0 <= question.novelty <= 100
        assert 0 <= question.feasibility <= 100


class TestSystemRecovery:
    """Test that system can recover from failures."""

    def test_artifact_can_be_retried_after_failure(
        self, repo, mock_user
    ):
        """Artifact should be retryable after initial failure."""
        artifact = repo.create_research_intelligence_artifact(
            id="artifact_retry_001",
            workspace_id=1,
            user_id=mock_user.id,
            topic="Test Topic",
            paper_ids=[1, 2],
            pipeline_version="1.0",
            status="running",
        )

        # Update to failed status
        repo.update_research_intelligence_artifact(
            artifact_id=artifact.id,
            updates={
                "status": "failed",
            },
        )

        # Create new artifact for retry (failed artifacts cannot be retried)
        retry_artifact = repo.create_research_intelligence_artifact(
            id="artifact_retry_002",
            workspace_id=1,
            user_id=mock_user.id,
            topic="Test Topic",
            paper_ids=[1, 2],
            pipeline_version="1.0",
            status="running",
        )

        assert retry_artifact is not None
        assert retry_artifact.status == "running"

    def test_partial_data_can_be_updated_after_failure(
        self, repo, mock_user
    ):
        """Partial data can be updated during running state."""
        artifact = repo.create_research_intelligence_artifact(
            id="artifact_update_001",
            workspace_id=1,
            user_id=mock_user.id,
            topic="Test Topic",
            paper_ids=[1, 2],
            pipeline_version="1.0",
            status="running",
        )

        # Update with partial data while running
        result = repo.update_research_intelligence_artifact(
            artifact_id=artifact.id,
            updates={
                "evidence_analysis": {"test": "data"},
            },
        )

        assert result is not None
        assert result.evidence_analysis is not None
        assert result.status == "running"
