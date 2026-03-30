from __future__ import annotations

from repositories.research import FirebaseResearchRepository, User


def _seed_workspace(repo: FirebaseResearchRepository, user: User) -> tuple[int, int]:
    workspace = repo.create_workspace(int(user.id), "Feed Router WS", "Router test workspace")
    paper = repo.create_paper(
        workspace_id=int(workspace.id),
        title="Router Feed Paper",
        authors="A. Author",
        abstract="Routing and feed generation test paper.",
        url="https://example.org/router-feed-paper",
    )
    repo.save(paper)
    return int(workspace.id), int(paper.id)


def test_workspace_feed_get_endpoint_maps_payload(
    test_client,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    workspace_id, paper_id = _seed_workspace(repo, mock_user)

    async def _fake_generate(**kwargs):  # type: ignore[no-untyped-def]
        return {"status": "completed", "job": {"job_id": "job_feed_1", "status": "completed"}}

    def _fake_page(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "items": [
                {
                    "feed_item_id": "wsf_1",
                    "type": "trend",
                    "title": "Emerging trend detected",
                    "description": "Trend details",
                    "related_papers": [paper_id],
                    "importance_score": 0.82,
                    "created_at": None,
                    "updated_at": None,
                    "read": False,
                    "read_at": None,
                    "source_refs": [1],
                    "sources": [
                        {
                            "source_index": 1,
                            "source_id": f"paper:{paper_id}",
                            "source_type": "paper",
                            "title": "Router Feed Paper",
                            "url": "https://example.org/router-feed-paper",
                            "doi": "",
                            "paper_id": paper_id,
                            "similarity_score": 0.91,
                        }
                    ],
                }
            ],
            "next_cursor": None,
            "total_count": 1,
            "unread_count": 1,
        }

    monkeypatch.setattr("routers.workspace_feed.get_or_generate_workspace_feed", _fake_generate)
    monkeypatch.setattr("routers.workspace_feed.get_workspace_feed_page", _fake_page)

    response = test_client.get(
        f"/workspace-feed/{workspace_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["workspace_id"] == workspace_id
    assert len(payload["items"]) == 1
    assert payload["items"][0]["related_papers"] == [paper_id]


def test_workspace_feed_mark_read_endpoint(
    test_client,
    auth_headers: dict,
    repo: FirebaseResearchRepository,
    mock_user: User,
    monkeypatch,
):
    workspace_id, paper_id = _seed_workspace(repo, mock_user)

    def _fake_mark(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "feed_item_id": "wsf_2",
            "type": "recommendation",
            "title": "Compare papers next",
            "description": "Action recommendation",
            "related_papers": [paper_id],
            "importance_score": 0.7,
            "created_at": None,
            "updated_at": None,
            "read": True,
            "read_at": None,
            "source_refs": [],
            "sources": [],
        }

    monkeypatch.setattr("routers.workspace_feed.mark_workspace_feed_item_read", _fake_mark)

    response = test_client.post(
        f"/workspace-feed/{workspace_id}/items/wsf_2/read",
        json={"read": True},
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["feed_item_id"] == "wsf_2"
    assert payload["read"] is True
