"""
services/cache_service.py
──────────────────────────
Two-tier AI response cache:

  Layer 1 — In-Memory dict (L1)
  ─────────────────────────────
  * Process-local dict ``_MEM_CACHE`` keyed by cache key.
  * TTL: ``AI_MEMORY_CACHE_TTL_SECONDS`` env var (default 30 s).
  * Max entries: ``_MEM_CACHE_MAXSIZE`` (512) — oldest entry evicted on overflow.
  * Thread-safe via ``_MEM_LOCK``.
  * Benefit: eliminates Firestore round-trips for repeated hot queries.

  Layer 2 — Firestore (L2)
  ─────────────────────────
  * Collection ``ai_cache/{sha256_key}``.
  * TTL enforced client-side: ``(now - created_at) > ttl_seconds`` → miss + lazy delete.
  * Firestore does NOT auto-expire; lazy invalidation keeps storage clean.
  * On L2 hit, backfill L1 so the next request is served from memory.

Call flow (ai_service.py handles orchestration):
  check L1 → HIT return (layer="memory")
  check L2 → HIT backfill L1, return (layer="firestore")
  MISS → call Groq → write L1 + L2, return (layer=None / fresh)

Cache key:
  SHA-256( user_id + ":" + normalize(query) )
  Per-user: two users asking the same question never share a cache entry.

Firestore schema — ai_cache/{key}
  response    : str       — AI response text (capped at 512 KB)
  created_at  : Timestamp — SERVER_TIMESTAMP on write
  ttl_seconds : int       — seconds until stale
  route       : str       — originating route (auditing)
  user_id     : str       — owner (auditing / manual invalidation)
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# ── TTL configuration ────────────────────────────────────────────────────────
# Firestore (L2) TTL — how long a Firestore entry is considered valid.
_DEFAULT_TTL: int = max(60, int(os.getenv("AI_CACHE_TTL_SECONDS", "3600") or 3600))

# In-memory (L1) TTL — short enough that cache is reasonably fresh.
_MEM_TTL: int = max(10, int(os.getenv("AI_MEMORY_CACHE_TTL_SECONDS", "30") or 30))

# Max entries in the in-memory cache (prevent unbounded growth).
_MEM_CACHE_MAXSIZE: int = 512

# Firestore document size limit guard.
_MAX_RESPONSE_CHARS: int = 512_000

# Routes that MUST NOT be cached (workspace-context-sensitive responses).
UNCACHEABLE_ROUTES: frozenset[str] = frozenset({"chat", "writing_chat"})

# ── In-memory cache (L1) ─────────────────────────────────────────────────────
# Entry format: (response_str, inserted_epoch_float)
_MEM_CACHE: dict[str, Tuple[str, float]] = {}
_MEM_LOCK = threading.Lock()


# ── Helpers: In-memory layer ─────────────────────────────────────────────────

def get_memory_cache(key: str) -> Optional[str]:
    """Return cached response from L1 (in-memory), or None on miss/expiry."""
    if not key:
        return None
    with _MEM_LOCK:
        entry = _MEM_CACHE.get(key)
        if entry is None:
            return None
        value, ts = entry
        if time.time() - ts > _MEM_TTL:
            _MEM_CACHE.pop(key, None)
            return None
        return value


def set_memory_cache(key: str, value: str) -> None:
    """Store a response in L1. Evicts the oldest entry when the cache is full."""
    if not key or not value:
        return
    with _MEM_LOCK:
        # Evict oldest entry if at capacity
        if len(_MEM_CACHE) >= _MEM_CACHE_MAXSIZE and key not in _MEM_CACHE:
            try:
                oldest_key = next(iter(_MEM_CACHE))
                _MEM_CACHE.pop(oldest_key, None)
            except StopIteration:
                pass
        _MEM_CACHE[key] = (value, time.time())


def invalidate_memory_cache(key: str) -> None:
    """Remove a single entry from L1."""
    if not key:
        return
    with _MEM_LOCK:
        _MEM_CACHE.pop(key, None)


# ── Helpers: query normalisation & key generation ────────────────────────────

def _normalize_query(query: str) -> str:
    """Collapse whitespace and lowercase a query to maximise cache hit rate."""
    return re.sub(r"\s+", " ", (query or "").strip()).lower()


def generate_cache_key(*, user_id: str, query: str) -> str:
    """Return a deterministic per-user SHA-256 cache key.

    Args:
        user_id: Authenticated user ID (string form).
        query:   Raw query / prompt sent to the LLM.

    Returns:
        64-character lowercase hex SHA-256 string.
    """
    normalized = _normalize_query(query)
    raw = f"{user_id}:{normalized}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── Firestore (L2) accessors ─────────────────────────────────────────────────

def get_cached_response(db, key: str) -> Optional[str]:
    """Look up a cached AI response in Firestore (L2).

    Performs client-side TTL check. On expiry, lazily deletes the stale
    document in a best-effort manner (does not block the caller).

    Args:
        db:  Firestore client (``repo.db``).
        key: Cache key from :func:`generate_cache_key`.

    Returns:
        Cached response string if valid, otherwise ``None``.
    """
    if not key:
        return None
    try:
        doc_ref = db.collection("ai_cache").document(key)
        doc = doc_ref.get()
        if not doc.exists:
            return None

        data = doc.to_dict() or {}
        response = data.get("response") or ""
        if not response:
            return None

        # Client-side TTL enforcement (Firestore does not auto-expire)
        created_at = data.get("created_at")
        ttl = int(data.get("ttl_seconds") or _DEFAULT_TTL)
        if created_at is not None:
            try:
                age_seconds = time.time() - created_at.timestamp()
                if age_seconds > ttl:
                    # Lazy invalidation — best effort, non-blocking
                    try:
                        doc_ref.delete()
                    except Exception:
                        pass
                    return None
            except Exception:
                pass  # Timestamp unreadable → treat as miss (safe)

        return str(response)
    except Exception as exc:  # pragma: no cover
        logger.warning("cache_service: get_cached_response failed: %s", exc)
        return None


def set_cached_response(
    db,
    key: str,
    response: str,
    *,
    route: str = "",
    user_id: str = "",
    ttl_seconds: Optional[int] = None,
) -> None:
    """Store an AI response in Firestore (L2) and backfill L1.

    No-ops silently if ``key`` or ``response`` is falsy.

    Args:
        db:          Firestore client.
        key:         Cache key from :func:`generate_cache_key`.
        response:    AI response string to cache.
        route:       Route identifier (stored for auditing).
        user_id:     Owner user ID (stored for auditing).
        ttl_seconds: TTL override. Defaults to ``AI_CACHE_TTL_SECONDS`` (3600).
    """
    if not key or not response:
        return
    try:
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP  # type: ignore

        db.collection("ai_cache").document(key).set(
            {
                "response": str(response)[:_MAX_RESPONSE_CHARS],
                "created_at": SERVER_TIMESTAMP,
                "ttl_seconds": int(ttl_seconds or _DEFAULT_TTL),
                "route": str(route or ""),
                "user_id": str(user_id or ""),
            }
        )
        # Backfill L1 so the next hot request is served from memory
        set_memory_cache(key, str(response)[:_MAX_RESPONSE_CHARS])
    except Exception as exc:  # pragma: no cover
        logger.warning("cache_service: set_cached_response failed: %s", exc)


def invalidate_cache_entry(db, key: str) -> None:
    """Explicitly delete a cache entry from both L1 and Firestore (L2).

    Args:
        db:  Firestore client.
        key: Cache key from :func:`generate_cache_key`.
    """
    if not key:
        return
    invalidate_memory_cache(key)
    try:
        db.collection("ai_cache").document(key).delete()
    except Exception as exc:  # pragma: no cover
        logger.warning("cache_service: invalidate_cache_entry failed: %s", exc)
