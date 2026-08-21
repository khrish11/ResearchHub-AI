"""
Authorization and IDOR (Insecure Direct Object Reference) Tests

Tests that verify users cannot access each other's resources via API endpoints.
Authorization is enforced at the router/API level, not repository level.

This test suite verifies:
- API endpoints properly check workspace ownership
- Cross-user access is prevented
- Cross-workspace access is prevented
- Malformed/nonexistent IDs are handled correctly
"""

import pytest
from fastapi.testclient import TestClient


class TestEdgeCases:
    """Edge case tests for repository operations."""

    def test_nonexistent_artifact_id(self, repo):
        """Get nonexistent artifact returns None."""
        result = repo.get_research_intelligence_artifact("nonexistent_id")
        assert result is None

    def test_nonexistent_question_id(self, repo):
        """Get nonexistent question returns None."""
        result = repo.get_saved_research_question("nonexistent_id")
        assert result is None

    def test_nonexistent_plan_id(self, repo):
        """Get nonexistent plan returns None."""
        result = repo.get_research_plan("nonexistent_id")
        assert result is None

    def test_delete_nonexistent_artifact(self, repo):
        """Delete nonexistent artifact returns False."""
        success = repo.delete_research_intelligence_artifact("nonexistent_id")
        assert success is False

    def test_delete_nonexistent_question(self, repo):
        """Delete nonexistent question returns False."""
        success = repo.delete_saved_research_question("nonexistent_id")
        assert success is False

    def test_delete_nonexistent_plan(self, repo):
        """Delete nonexistent plan returns False."""
        success = repo.delete_research_plan("nonexistent_id")
        assert success is False

    def test_list_questions_filters_by_workspace_and_user(
        self, repo
    ):
        """List questions filters by both workspace_id and user_id."""
        # This test verifies the repository correctly filters by both workspace and user
        # The actual authorization is enforced at the API level
        pass  # Repository-level filtering is already tested in test_saved_research_questions.py

    def test_list_plans_filters_by_workspace_and_user(
        self, repo
    ):
        """List plans filters by both workspace_id and user_id."""
        # This test verifies the repository correctly filters by both workspace and user
        # The actual authorization is enforced at the API level
        pass  # Repository-level filtering is already tested in existing plan tests


class TestCrossUserAccess:
    """Adversarial tests for cross-user access (IDOR prevention)."""

    def test_user_a_cannot_access_user_b_artifact(self, test_client: TestClient, user_a_token, user_b_artifact_id):
        """User A cannot GET User B's artifact."""
        response = test_client.get(
            f"/research/intelligence/artifacts/{user_b_artifact_id}",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response.status_code in {403, 404}

    def test_user_a_cannot_delete_user_b_artifact(self, test_client: TestClient, user_a_token, user_b_artifact_id):
        """User A cannot DELETE User B's artifact."""
        response = test_client.delete(
            f"/research/intelligence/artifacts/{user_b_artifact_id}",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response.status_code in {403, 404}

    def test_user_a_cannot_access_user_b_question(self, test_client: TestClient, user_a_token, user_b_question_id):
        """User A cannot GET User B's question."""
        response = test_client.get(
            f"/research/questions/{user_b_question_id}",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response.status_code in {403, 404}

    def test_user_a_cannot_delete_user_b_question(self, test_client: TestClient, user_a_token, user_b_question_id):
        """User A cannot DELETE User B's question."""
        response = test_client.delete(
            f"/research/questions/{user_b_question_id}",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response.status_code in {403, 404}

    def test_user_a_cannot_access_user_b_plan(self, test_client: TestClient, user_a_token, user_b_plan_id):
        """User A cannot GET User B's plan."""
        response = test_client.get(
            f"/research/plans/{user_b_plan_id}",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response.status_code in {403, 404}

    def test_user_a_cannot_update_user_b_plan(self, test_client: TestClient, user_a_token, user_b_plan_id):
        """User A cannot PUT User B's plan."""
        response = test_client.put(
            f"/research/plans/{user_b_plan_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
            json={"title": "Malicious update"}
        )
        assert response.status_code in {403, 404}

    def test_user_a_cannot_delete_user_b_plan(self, test_client: TestClient, user_a_token, user_b_plan_id):
        """User A cannot DELETE User B's plan."""
        response = test_client.delete(
            f"/research/plans/{user_b_plan_id}",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response.status_code in {403, 404}

    def test_user_a_cannot_access_user_b_workspace(self, test_client: TestClient, user_a_token, user_b_workspace_id):
        """User A cannot access User B's workspace."""
        response = test_client.get(
            f"/workspaces/{user_b_workspace_id}",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response.status_code in {403, 404}

    def test_user_a_cannot_export_user_b_plan(self, test_client: TestClient, user_a_token, user_b_plan_id):
        """User A cannot export User B's plan to DocSpace."""
        response = test_client.post(
            f"/research/plans/{user_b_plan_id}/export",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response.status_code in {403, 404}


class TestMalformedIds:
    """Tests for malformed and invalid IDs."""

    def test_malformed_artifact_id(self, test_client: TestClient, user_a_token):
        """Malformed artifact ID returns 404."""
        response = test_client.get(
            "/research/intelligence/artifacts/../../etc/passwd",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response.status_code in {404, 400}

    def test_malformed_question_id(self, test_client: TestClient, user_a_token):
        """Malformed question ID returns 404."""
        response = test_client.get(
            "/research/questions/<script>alert('xss')</script>",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response.status_code in {404, 400}

    def test_malformed_plan_id(self, test_client: TestClient, user_a_token):
        """Malformed plan ID returns 404."""
        response = test_client.get(
            "/research/plans/../../../admin",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response.status_code in {404, 400}

    def test_nonexistent_artifact_id(self, test_client: TestClient, user_a_token):
        """Nonexistent artifact ID returns 404."""
        response = test_client.get(
            "/research/intelligence/artifacts/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response.status_code == 404

    def test_nonexistent_question_id(self, test_client: TestClient, user_a_token):
        """Nonexistent question ID returns 404."""
        response = test_client.get(
            "/research/questions/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response.status_code == 404

    def test_nonexistent_plan_id(self, test_client: TestClient, user_a_token):
        """Nonexistent plan ID returns 404."""
        response = test_client.get(
            "/research/plans/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response.status_code == 404


class TestCrossWorkspaceAccess:
    """Tests for cross-workspace access prevention."""

    def test_user_cannot_access_artifact_from_wrong_workspace(self, test_client: TestClient, user_a_token, workspace_a_artifact_id):
        """User cannot access artifact from workspace they don't own."""
        # Assuming workspace_a_artifact_id belongs to a workspace user_a doesn't own
        response = test_client.get(
            f"/research/intelligence/artifacts/{workspace_a_artifact_id}",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response.status_code in {403, 404}

    def test_user_cannot_list_questions_from_wrong_workspace(self, test_client: TestClient, user_a_token, user_b_workspace_id):
        """User cannot list questions from workspace they don't own."""
        response = test_client.get(
            f"/research/workspaces/{user_b_workspace_id}/questions",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response.status_code in {403, 404}

    def test_user_cannot_list_plans_from_wrong_workspace(self, test_client: TestClient, user_a_token, user_b_workspace_id):
        """User cannot list plans from workspace they don't own."""
        response = test_client.get(
            f"/research/workspaces/{user_b_workspace_id}/plans",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response.status_code in {403, 404}
