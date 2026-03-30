from __future__ import annotations

from repositories.research import FirebaseResearchRepository, User


def test_onboarding_status_for_empty_workspace_flow(
    test_client,
    auth_headers: dict,
) -> None:
    response = test_client.get("/onboarding/status", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert int(payload.get("workspace_id") or 0) > 0
    assert payload.get("paper_count") == 0
    assert payload.get("needs_onboarding") is True
    assert payload.get("has_completed_onboarding") is False
    assert len(payload.get("steps") or []) == 4
    assert len((payload.get("demo") or {}).get("sample_feed_items") or []) >= 1
    assert "Summarize this paper" in (payload.get("copilot_prompts") or [])


def test_onboarding_demo_bootstrap_seeds_workspace_data(
    test_client,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
) -> None:
    workspace = repo.create_workspace(int(mock_user.id or 0), "Onboarding Demo WS")

    response = test_client.post(
        "/onboarding/demo/bootstrap",
        headers=auth_headers,
        json={"workspace_id": int(workspace.id)},
    )
    assert response.status_code == 200
    payload = response.json()
    assert int(payload.get("workspace_id") or 0) == int(workspace.id)
    assert len(payload.get("paper_ids") or []) >= 3
    assert payload.get("seeded_feed_items", 0) >= 1

    status = payload.get("status") or {}
    assert status.get("demo", {}).get("seeded") is True
    assert int(status.get("paper_count") or 0) >= 3
    assert "upload_paper" in (status.get("completed_steps") or [])

    feed_response = test_client.get(f"/workspace-feed/{workspace.id}", headers=auth_headers)
    assert feed_response.status_code == 200
    feed_payload = feed_response.json()
    assert len(feed_payload.get("items") or []) >= 1


def test_onboarding_completion_sets_user_flag(
    test_client,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
) -> None:
    workspace = repo.create_workspace(int(mock_user.id or 0), "Onboarding Completion WS")
    repo.create_paper(
        workspace_id=int(workspace.id),
        title="Seed Paper",
        authors="A. Author",
        abstract="Abstract text for onboarding completion.",
        url="https://example.org/seed-paper",
    )

    for step_id in ("explain_paper", "compare_papers", "generate_report"):
        response = test_client.post(
            f"/onboarding/steps/{step_id}/complete",
            headers=auth_headers,
            json={"workspace_id": int(workspace.id)},
        )
        assert response.status_code == 200

    status = test_client.get(
        f"/onboarding/status?workspace_id={workspace.id}",
        headers=auth_headers,
    )
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload.get("has_completed_onboarding") is True
    assert float(status_payload.get("progress") or 0.0) >= 1.0

    me_response = test_client.get("/auth/me", headers=auth_headers)
    assert me_response.status_code == 200
    me_payload = me_response.json()
    assert me_payload.get("has_completed_onboarding") is True

