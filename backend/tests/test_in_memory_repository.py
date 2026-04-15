from __future__ import annotations

from repositories.research import InMemoryResearchRepository, User


def test_in_memory_save_user_without_id_assigns_new_id() -> None:
    repo = InMemoryResearchRepository()

    user = User(
        id=None,
        email="google-user@test.com",
        google_id="google-sub-123",
        google_email="google-user@test.com",
        name="Google User",
        is_verified=True,
    )

    saved = repo.save(user)

    assert isinstance(saved, User)
    assert saved.id is not None
    assert int(saved.id) > 0

    fetched = repo.get_user_by_google_id("google-sub-123")
    assert fetched is not None
    assert fetched.id == saved.id
