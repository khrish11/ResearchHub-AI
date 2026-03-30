"""
services/analytics_service.py
──────────────────────────────
Fire-and-forget AI usage tracking.

Every AI call across the platform (research agent, chat, analysis) is logged
to the Firestore ``ai_usage`` collection.  The write is non-blocking — any
failure is silently swallowed after logging a warning so a slow/unavailable
Firestore never degrades the user-facing response.

Firestore schema
────────────────
ai_usage/{auto_id}
  user_id          : str          — authenticated user's ID (as string)
  route            : str          — logical route name, e.g. "research_agent",
                                   "chat", "analyze", "gap_detection" …
  input_size       : int          — number of characters sent to the LLM
  output_size      : int          — number of characters returned by the LLM
  response_time_ms : int          — wall-clock time for the full LLM call(s)
  status           : str          — "success" | "error" | "cache_hit"
  model            : str          — Groq model name that was invoked
  cache_hit        : bool         — True when the response was served from cache
  created_at       : Timestamp    — server timestamp

Usage
─────
    from services.analytics_service import log_ai_usage
    log_ai_usage(
        db,
        user_id="42",
        route="analyze",
        input_size=len(prompt),
        output_size=len(response),
        duration_ms=730,
        status="success",
        model="llama-3.3-70b-versatile",
        cache_hit=False,
    )
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from google.cloud.firestore_v1.base_query import FieldFilter

logger = logging.getLogger(__name__)


def log_ai_usage(
    db,
    *,
    user_id: str,
    route: str,
    input_size: int,
    output_size: int,
    duration_ms: int,
    status: str = "success",
    model: str = "",
    cache_hit: bool = False,
) -> None:
    """Write a single AI usage record to Firestore in a background thread.

    Args:
        db:              Firestore client (``repo.db`` or direct client).
        user_id:         String representation of the authenticated user's ID.
        route:           Logical route identifier (e.g. ``"analyze"``,
                         ``"chat"``, ``"research_agent"``).
        input_size:      Characters sent to the LLM.
        output_size:     Characters returned by the LLM.
        duration_ms:     Wall-clock duration of the AI call in milliseconds.
                         Pass 0 on cache hits.
        status:          ``"success"``, ``"error"``, or ``"cache_hit"``.
        model:           Groq model name (empty string when served from cache).
        cache_hit:       Whether this usage was served from the response cache.
    """
    def _write() -> None:
        try:
            # Late import to avoid circular deps / slow startup in tests
            from google.cloud.firestore_v1 import SERVER_TIMESTAMP  # type: ignore

            db.collection("ai_usage").add(
                {
                    "user_id": str(user_id or ""),
                    "route": str(route or ""),
                    "input_size": max(0, int(input_size or 0)),
                    "output_size": max(0, int(output_size or 0)),
                    "response_time_ms": max(0, int(duration_ms or 0)),
                    "status": str(status or "success"),
                    "model": str(model or ""),
                    "cache_hit": bool(cache_hit),
                    "created_at": SERVER_TIMESTAMP,
                }
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("analytics_service: failed to log AI usage: %s", exc)

    # Run off the request thread so a slow Firestore write never adds latency.
    threading.Thread(target=_write, daemon=True).start()


def get_ai_usage_stats(db, *, user_id: Optional[str] = None, limit: int = 500) -> list:
    """Return recent AI usage records (admin/developer use).

    Args:
        db:       Firestore client.
        user_id:  Filter to a specific user. ``None`` returns all users.
        limit:    Maximum number of records to return (max 500).
    """
    try:
        query = db.collection("ai_usage").order_by(
            "created_at", direction="DESCENDING"
        ).limit(min(limit, 500))
        if user_id:
            query = query.where(
                filter=FieldFilter("user_id", "==", str(user_id))
            )
        docs = query.stream()
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
    except Exception as exc:  # pragma: no cover
        logger.warning("analytics_service: get_ai_usage_stats failed: %s", exc)
        return []
