"""
utils/user_cache.py — Thread-safe TTL in-memory cache for User objects.

Eliminates the Firestore read on every authenticated API request.
Entries expire after USER_CACHE_TTL_SECONDS (default: 30 s) so that
account mutations (password reset, de-activation, role change) take
effect quickly without a server restart.

Usage
-----
    from utils.user_cache import get_cached_user, invalidate_user_cache

    # Inside get_current_user dependency:
    user = get_cached_user(email, lambda e: repo.get_user_by_email(e))

    # After updating a user:
    invalidate_user_cache(user.email)
"""

from __future__ import annotations

import os
import time
from threading import Lock
from typing import Any, Callable, Optional

# How long (seconds) a user object stays in cache before we re-fetch from Firestore.
USER_CACHE_TTL_SECONDS: int = max(
    5, int(os.getenv("USER_CACHE_TTL_SECONDS", "30") or 30)
)
# Hard cap on cache size to avoid unbounded memory growth.
USER_CACHE_MAX_ENTRIES: int = max(
    100, int(os.getenv("USER_CACHE_MAX_ENTRIES", "2000") or 2000)
)

# Internal storage: email (normalized) → (user_object, insert_timestamp)
_CACHE: dict[str, tuple[Any, float]] = {}
_LOCK = Lock()


def get_cached_user(
    email: str,
    fetch_fn: Callable[[str], Optional[Any]],
) -> Optional[Any]:
    """Return a cached User or fetch it via *fetch_fn* and cache the result.

    Args:
        email:    Normalized (lowercase, stripped) user email — used as cache key.
        fetch_fn: Callable that accepts the email string and returns a User or None.

    Returns:
        User object, or None if the user does not exist.
    """
    key = str(email or "").strip().lower()
    if not key:
        return None

    now = time.monotonic()

    with _LOCK:
        entry = _CACHE.get(key)
        if entry is not None:
            user_obj, inserted_at = entry
            if (now - inserted_at) < USER_CACHE_TTL_SECONDS:
                return user_obj
            # Expired — remove stale entry
            _CACHE.pop(key, None)

    # Cache miss — fetch from Firestore
    user = fetch_fn(key)

    with _LOCK:
        # Evict oldest entries if over the size cap
        if len(_CACHE) >= USER_CACHE_MAX_ENTRIES:
            oldest_key = min(_CACHE, key=lambda k: _CACHE[k][1])
            _CACHE.pop(oldest_key, None)

        if user is not None:
            _CACHE[key] = (user, now)

    return user


def invalidate_user_cache(email: str) -> None:
    """Remove a specific user from the cache immediately.

    Call this after any mutation that changes user state (password change,
    role upgrade, account deactivation, email verification, etc.).
    """
    key = str(email or "").strip().lower()
    with _LOCK:
        _CACHE.pop(key, None)


def clear_user_cache() -> None:
    """Flush all entries from the cache. Useful in tests."""
    with _LOCK:
        _CACHE.clear()


def user_cache_stats() -> dict[str, Any]:
    """Return current cache statistics for the /ops/metrics endpoint."""
    with _LOCK:
        now = time.monotonic()
        total = len(_CACHE)
        active = sum(
            1
            for _, (_, ts) in _CACHE.items()
            if (now - ts) < USER_CACHE_TTL_SECONDS
        )
    return {
        "user_cache_total_entries": total,
        "user_cache_active_entries": active,
        "user_cache_ttl_seconds": USER_CACHE_TTL_SECONDS,
        "user_cache_max_entries": USER_CACHE_MAX_ENTRIES,
    }
