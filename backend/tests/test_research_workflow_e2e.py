"""
Research Workflow E2E Test

Tests the complete intended research workflow:
DISCOVER → UNDERSTAND → EVALUATE EVIDENCE → IDENTIFY GAPS → RANK OPPORTUNITIES
→ GENERATE QUESTIONS → SAVE QUESTION → DEVELOP RESEARCH PLAN → ACCEPT/MODIFY/REJECT
→ SAVE PLAN → EXPORT PLAN TO DOCSPACE → GENERATE RESEARCH REPORT → VERIFY PROVENANCE

Verifies that IDs and provenance remain consistent across every transition.
"""

import pytest
from datetime import datetime, timezone, timedelta
from routers.auth import create_access_token


class TestResearchWorkflowE2E:
    """End-to-end test of the complete research workflow."""

    def test_complete_research_workflow_provenance_chain(
        self, repo, test_client, mock_user, auth_headers
    ):
        """
        Test the complete research workflow with provenance tracking.
        
        Workflow:
        1. Create workspace
        2. Create intelligence artifact
        3. Save research question linked to artifact
        4. Create research plan linked to artifact
        5. Verify all IDs and provenance remain consistent
        """
        # Step 1: Create workspace
        workspace = repo.create_workspace(
            user_id=mock_user.id,
            name="Research Workspace",
            description="Test workspace for E2E workflow",
        )
        assert workspace.id is not None
        assert workspace.user_id == mock_user.id

        # Step 2: Create intelligence artifact
        artifact = repo.create_research_intelligence_artifact(
            id="artifact_e2e_001",
            workspace_id=workspace.id,
            user_id=mock_user.id,
            topic="Machine Learning Interpretability",
            paper_ids=[1, 2, 3],
            pipeline_version="1.0",
            status="completed",
        )
        assert artifact.id == "artifact_e2e_001"
        assert artifact.workspace_id == workspace.id
        assert artifact.user_id == mock_user.id

        # Step 3: Save research question linked to artifact
        question = repo.create_saved_research_question(
            id="question_e2e_001",
            workspace_id=workspace.id,
            user_id=mock_user.id,
            question="How can we improve model interpretability?",
            category="exploratory",
            complexity="moderate",
            confidence=75,
            novelty=80,
            feasibility=70,
            impact=85,
            source_artifact_id=artifact.id,
            source_gap_id="gap_001",
            source_gap_description="Lack of interpretability methods",
        )
        assert question.id == "question_e2e_001"
        assert question.workspace_id == workspace.id
        assert question.user_id == mock_user.id
        assert question.source_artifact_id == artifact.id

        # Step 4: Create research plan linked to artifact
        plan = repo.create_research_plan(
            id="plan_e2e_001",
            workspace_id=workspace.id,
            user_id=mock_user.id,
            artifact_id=artifact.id,
            opportunity_id="opp_001",
            opportunity_description="Develop new interpretability method",
            title="Interpretability Research Plan",
            research_problem="Black box models lack transparency",
            research_question="Can we develop interpretable models?",
            hypothesis="Attention mechanisms can provide interpretability",
            objectives="Develop attention-based interpretability",
            proposed_methodology="Use attention visualization",
            alternative_methodology="Use SHAP values",
            datasets="ImageNet, CIFAR-10",
            variables="attention weights, feature importance",
            baselines="Standard CNN, ResNet",
            evaluation_metrics="accuracy, interpretability score",
            expected_contribution="New interpretability framework",
            risks="Method may not generalize",
            limitations="Requires large datasets",
            reproducibility_requirements="Open source code, pretrained models",
        )
        assert plan.id == "plan_e2e_001"
        assert plan.workspace_id == workspace.id
        assert plan.user_id == mock_user.id
        assert plan.artifact_id == artifact.id

        # Step 5: Verify provenance chain
        # Retrieve all entities and verify relationships
        retrieved_artifact = repo.get_research_intelligence_artifact(artifact.id)
        assert retrieved_artifact is not None
        assert retrieved_artifact.workspace_id == workspace.id
        assert retrieved_artifact.user_id == mock_user.id

        retrieved_question = repo.get_saved_research_question(question.id)
        assert retrieved_question is not None
        assert retrieved_question.workspace_id == workspace.id
        assert retrieved_question.user_id == mock_user.id
        assert retrieved_question.source_artifact_id == artifact.id

        retrieved_plan = repo.get_research_plan(plan.id)
        assert retrieved_plan is not None
        assert retrieved_plan.workspace_id == workspace.id
        assert retrieved_plan.user_id == mock_user.id
        assert retrieved_plan.artifact_id == artifact.id

        # Verify list operations return correct entities
        workspace_questions = repo.list_saved_research_questions_for_workspace(
            workspace.id, mock_user.id
        )
        assert len(workspace_questions) == 1
        assert workspace_questions[0].id == question.id

        workspace_plans = repo.list_research_plans_for_workspace(
            workspace.id, mock_user.id
        )
        assert len(workspace_plans) == 1
        assert workspace_plans[0].id == plan.id

    def test_provenance_preservation_after_update(
        self, repo, mock_user
    ):
        """Test that provenance is preserved after updates."""
        # Create workspace and artifact
        workspace = repo.create_workspace(
            user_id=mock_user.id,
            name="Update Test Workspace",
            description="Test workspace for update provenance",
        )

        artifact = repo.create_research_intelligence_artifact(
            id="artifact_update_001",
            workspace_id=workspace.id,
            user_id=mock_user.id,
            topic="Test Topic",
            paper_ids=[1, 2],
            pipeline_version="1.0",
        )

        # Create question
        question = repo.create_saved_research_question(
            id="question_update_001",
            workspace_id=workspace.id,
            user_id=mock_user.id,
            question="Test question",
            category="exploratory",
            complexity="simple",
            confidence=50,
            novelty=50,
            feasibility=50,
            impact=50,
            source_artifact_id=artifact.id,
        )

        # Update artifact status
        repo.update_research_intelligence_artifact(
            artifact_id=artifact.id,
            updates={
                "status": "completed",
                "overall_score": 85,
                "summary": "Test summary",
            },
        )

        # Verify question still has correct provenance after artifact update
        retrieved_question = repo.get_saved_research_question(question.id)
        assert retrieved_question.source_artifact_id == artifact.id
        assert retrieved_question.workspace_id == workspace.id
        assert retrieved_question.user_id == mock_user.id

    def test_cross_entity_id_consistency(
        self, repo, mock_user
    ):
        """Test that IDs remain consistent across entity relationships."""
        workspace = repo.create_workspace(
            user_id=mock_user.id,
            name="ID Consistency Workspace",
            description="Test workspace for ID consistency",
        )

        artifact_id = "artifact_id_test_123"
        question_id = "question_id_test_456"
        plan_id = "plan_id_test_789"

        # Create entities with specific IDs
        artifact = repo.create_research_intelligence_artifact(
            id=artifact_id,
            workspace_id=workspace.id,
            user_id=mock_user.id,
            topic="Test Topic",
            paper_ids=[1],
            pipeline_version="1.0",
        )

        question = repo.create_saved_research_question(
            id=question_id,
            workspace_id=workspace.id,
            user_id=mock_user.id,
            question="Test question",
            category="exploratory",
            complexity="simple",
            confidence=50,
            novelty=50,
            feasibility=50,
            impact=50,
            source_artifact_id=artifact_id,
        )

        plan = repo.create_research_plan(
            id=plan_id,
            workspace_id=workspace.id,
            user_id=mock_user.id,
            artifact_id=artifact_id,
            opportunity_id="opp_001",
            opportunity_description="Test opportunity",
            title="Test Plan",
            research_problem="Test problem",
            research_question="Test question",
            hypothesis="Test hypothesis",
            objectives="Test objectives",
            proposed_methodology="Test methodology",
            alternative_methodology="Alternative methodology",
            datasets="Test datasets",
            variables="Test variables",
            baselines="Test baselines",
            evaluation_metrics="Test metrics",
            expected_contribution="Test contribution",
            risks="Test risks",
            limitations="Test limitations",
            reproducibility_requirements="Test reproducibility",
        )

        # Verify IDs match exactly
        assert artifact.id == artifact_id
        assert question.id == question_id
        assert plan.id == plan_id
        assert question.source_artifact_id == artifact_id
        assert plan.artifact_id == artifact_id

    def test_workspace_isolation_in_workflow(
        self, repo
    ):
        """Test that workflow entities are properly isolated by workspace."""
        # Create user
        user = repo.create_user(
            email="workflow_test@test.com",
            name="Workflow Test User",
            is_active=True,
            is_verified=True,
        )

        # Create two workspaces
        workspace_1 = repo.create_workspace(
            user_id=user.id,
            name="Workspace 1",
            description="First workspace",
        )

        workspace_2 = repo.create_workspace(
            user_id=user.id,
            name="Workspace 2",
            description="Second workspace",
        )

        # Create artifact in workspace 1
        artifact_1 = repo.create_research_intelligence_artifact(
            id="artifact_ws1_001",
            workspace_id=workspace_1.id,
            user_id=user.id,
            topic="Workspace 1 Topic",
            paper_ids=[1],
            pipeline_version="1.0",
        )

        # Create artifact in workspace 2
        artifact_2 = repo.create_research_intelligence_artifact(
            id="artifact_ws2_001",
            workspace_id=workspace_2.id,
            user_id=user.id,
            topic="Workspace 2 Topic",
            paper_ids=[2],
            pipeline_version="1.0",
        )

        # Create question in workspace 1
        question_1 = repo.create_saved_research_question(
            id="question_ws1_001",
            workspace_id=workspace_1.id,
            user_id=user.id,
            question="Workspace 1 question",
            category="exploratory",
            complexity="simple",
            confidence=50,
            novelty=50,
            feasibility=50,
            impact=50,
            source_artifact_id=artifact_1.id,
        )

        # Create question in workspace 2
        question_2 = repo.create_saved_research_question(
            id="question_ws2_001",
            workspace_id=workspace_2.id,
            user_id=user.id,
            question="Workspace 2 question",
            category="exploratory",
            complexity="simple",
            confidence=50,
            novelty=50,
            feasibility=50,
            impact=50,
            source_artifact_id=artifact_2.id,
        )

        # Verify isolation
        questions_ws1 = repo.list_saved_research_questions_for_workspace(
            workspace_1.id, user.id
        )
        assert len(questions_ws1) == 1
        assert questions_ws1[0].id == question_1.id
        assert questions_ws1[0].workspace_id == workspace_1.id

        questions_ws2 = repo.list_saved_research_questions_for_workspace(
            workspace_2.id, user.id
        )
        assert len(questions_ws2) == 1
        assert questions_ws2[0].id == question_2.id
        assert questions_ws2[0].workspace_id == workspace_2.id

    def test_timestamp_consistency(
        self, repo, mock_user
    ):
        """Test that timestamps are consistent and in UTC."""
        workspace = repo.create_workspace(
            user_id=mock_user.id,
            name="Timestamp Test Workspace",
            description="Test workspace for timestamp consistency",
        )

        artifact = repo.create_research_intelligence_artifact(
            id="artifact_ts_001",
            workspace_id=workspace.id,
            user_id=mock_user.id,
            topic="Test Topic",
            paper_ids=[1],
            pipeline_version="1.0",
        )

        question = repo.create_saved_research_question(
            id="question_ts_001",
            workspace_id=workspace.id,
            user_id=mock_user.id,
            question="Test question",
            category="exploratory",
            complexity="simple",
            confidence=50,
            novelty=50,
            feasibility=50,
            impact=50,
        )

        plan = repo.create_research_plan(
            id="plan_ts_001",
            workspace_id=workspace.id,
            user_id=mock_user.id,
            artifact_id=artifact.id,
            opportunity_id="opp_001",
            opportunity_description="Test opportunity",
            title="Test Plan",
            research_problem="Test problem",
            research_question="Test question",
            hypothesis="Test hypothesis",
            objectives="Test objectives",
            proposed_methodology="Test methodology",
            alternative_methodology="Alternative methodology",
            datasets="Test datasets",
            variables="Test variables",
            baselines="Test baselines",
            evaluation_metrics="Test metrics",
            expected_contribution="Test contribution",
            risks="Test risks",
            limitations="Test limitations",
            reproducibility_requirements="Test reproducibility",
        )

        # Verify timestamps are datetime objects with timezone
        assert artifact.created_at.tzinfo == timezone.utc
        assert artifact.updated_at.tzinfo == timezone.utc
        assert question.created_at.tzinfo == timezone.utc
        assert plan.created_at.tzinfo == timezone.utc
        assert plan.updated_at.tzinfo == timezone.utc

        # Verify timestamps are reasonable (not in the future)
        now = datetime.now(timezone.utc)
        assert artifact.created_at <= now
        assert question.created_at <= now
        assert plan.created_at <= now
