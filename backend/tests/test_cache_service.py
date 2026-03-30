from __future__ import annotations

from services.cache_service import generate_cache_key


def test_generate_cache_key_is_user_and_scope_sensitive() -> None:
    key_a = generate_cache_key(user_id="1", query="What is RAG?", scope='{"route":"chat"}')
    key_b = generate_cache_key(user_id="1", query="What is RAG?", scope='{"route":"report"}')
    key_c = generate_cache_key(user_id="2", query="What is RAG?", scope='{"route":"chat"}')

    assert key_a != key_b
    assert key_a != key_c


def test_generate_cache_key_normalizes_query_and_scope() -> None:
    key_a = generate_cache_key(
        user_id="9",
        query="  Summarize   my workspace ",
        scope='{"route":"chat","model":"x"}',
    )
    key_b = generate_cache_key(
        user_id="9",
        query="summarize my workspace",
        scope='{"route":"chat","model":"x"}',
    )
    assert key_a == key_b
