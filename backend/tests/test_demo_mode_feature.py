from __future__ import annotations

from repositories.research import FirebaseResearchRepository, User


def test_demo_mode_start_bootstraps_reusable_scenario(
    test_client,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
) -> None:
    workspace = repo.create_workspace(int(mock_user.id or 0), "Demo Scenario WS")
    response = test_client.post(
        "/demo/start",
        headers=auth_headers,
        json={"workspace_id": int(workspace.id)},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("is_demo_mode") is True
    assert int(payload.get("workspace_id") or 0) == int(workspace.id)
    assert int(payload.get("paper_count") or 0) >= 3
    assert len(payload.get("steps") or []) == 5
    assert payload.get("comparison_id")
    assert payload.get("report_id")
    assert payload.get("insight_id")

    state = test_client.get(
        f"/demo/state?workspace_id={workspace.id}",
        headers=auth_headers,
    )
    assert state.status_code == 200
    state_payload = state.json()
    assert state_payload.get("is_demo_mode") is True


def test_demo_mode_step_navigation_and_completion(
    test_client,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
) -> None:
    workspace = repo.create_workspace(int(mock_user.id or 0), "Demo Step WS")
    start = test_client.post(
        "/demo/start",
        headers=auth_headers,
        json={"workspace_id": int(workspace.id)},
    )
    assert start.status_code == 200
    start_payload = start.json()
    first_step = str(start_payload.get("current_step") or "")
    assert first_step == "explain_paper"

    complete = test_client.post(
        "/demo/steps/complete",
        headers=auth_headers,
        json={"workspace_id": int(workspace.id), "step_id": first_step},
    )
    assert complete.status_code == 200
    complete_payload = complete.json()
    assert first_step in (complete_payload.get("completed_steps") or [])
    assert str(complete_payload.get("current_step") or "") == "compare_papers"

    advance = test_client.post(
        "/demo/steps/next",
        headers=auth_headers,
        json={"workspace_id": int(workspace.id)},
    )
    assert advance.status_code == 200
    advance_payload = advance.json()
    assert "compare_papers" in (advance_payload.get("completed_steps") or [])
    assert str(advance_payload.get("current_step") or "") == "generate_report"


def test_demo_mode_exit_behavior(
    test_client,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
) -> None:
    workspace = repo.create_workspace(int(mock_user.id or 0), "Demo Exit WS")
    started = test_client.post(
        "/demo/start",
        headers=auth_headers,
        json={"workspace_id": int(workspace.id)},
    )
    assert started.status_code == 200
    assert started.json().get("is_demo_mode") is True

    exited = test_client.post(
        "/demo/exit",
        headers=auth_headers,
        json={"workspace_id": int(workspace.id)},
    )
    assert exited.status_code == 200
    exit_payload = exited.json()
    assert exit_payload.get("is_demo_mode") is False
    assert exit_payload.get("exited_at")

    state = test_client.get(
        f"/demo/state?workspace_id={workspace.id}",
        headers=auth_headers,
    )
    assert state.status_code == 200
    state_payload = state.json()
    assert state_payload.get("is_demo_mode") is False
