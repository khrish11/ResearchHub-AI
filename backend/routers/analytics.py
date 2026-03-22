"""
routers/analytics.py
─────────────────────
Admin-only analytics API endpoints backed by the ai_usage Firestore collection.

All endpoints:
  • Require a valid authenticated user whose ID appears in ADMIN_USER_IDS.
  • Return the standard envelope: {"data": ..., "meta": {"generated_at": ...}}.
  • Are backed by analytics_query_service.py which applies 60s result caching
    and bounded Firestore queries (max 1000 docs per call).

Environment
───────────
  ADMIN_USER_IDS  — comma-separated list of user IDs allowed to call these
                    endpoints. If empty/unset, the endpoints return 403 for
                    every authenticated user. Set this in backend/.env.

Example:
  ADMIN_USER_IDS=uid_abc123,uid_def456
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from repositories import ResearchRepository, get_research_repository
from repositories.research import User
from routers.auth import get_current_user
from services.analytics_query_service import (
    get_global_stats,
    get_route_stats,
    get_top_users,
    get_usage_timeseries,
    get_user_usage,
    invalidate_analytics_cache,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

# ── Admin guard ───────────────────────────────────────────────────────────────

def _load_admin_ids() -> set[str]:
    raw = os.getenv("ADMIN_USER_IDS", "").strip()
    return {uid.strip() for uid in raw.split(",") if uid.strip()}


def _require_admin(current_user: User) -> None:
    """Raise 403 if the user is not in the ADMIN_USER_IDS whitelist."""
    admin_ids = _load_admin_ids()
    if not admin_ids:
        raise HTTPException(
            status_code=403,
            detail="Analytics access is disabled. Set ADMIN_USER_IDS in backend/.env.",
        )
    user_id = str(getattr(current_user, "id", "") or "")
    if user_id not in admin_ids:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access analytics.",
        )


# ── Response wrapper ──────────────────────────────────────────────────────────

def _wrap(data: Any) -> Dict[str, Any]:
    return {
        "data": data,
        "meta": {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        },
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/user")
def analytics_user(
    user_id: Optional[str] = Query(
        default=None,
        description="User ID to inspect. Defaults to the calling admin user.",
    ),
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """
    Return aggregated AI usage stats for a specific user.

    Returns total queries, cache hit rate, average response time, error count,
    and per-route breakdown.
    """
    _require_admin(current_user)
    target_uid = str(user_id or getattr(current_user, "id", "")).strip()
    if not target_uid:
        raise HTTPException(status_code=400, detail="user_id is required.")

    data = get_user_usage(repo.db, target_uid)
    return _wrap(data)


@router.get("/global")
def analytics_global(
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """
    Return platform-wide AI usage statistics.

    Aggregates across the most recent 1000 usage records: totals, error rate,
    cache hit rate, unique users, and average response time.
    """
    _require_admin(current_user)
    data = get_global_stats(repo.db)
    return _wrap(data)


@router.get("/top-users")
def analytics_top_users(
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Number of top users to return (1–100).",
    ),
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """
    Return the top N users ranked by total AI query count.

    Each entry includes cache hit rate, error count, and average response time.
    """
    _require_admin(current_user)
    data = get_top_users(repo.db, limit=limit)
    return _wrap(data)


@router.get("/routes")
def analytics_routes(
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """
    Return AI usage breakdown per logical route.

    Routes include: analyze, chat, research_agent, gap_detection, etc.
    Each entry shows call count, cache hit rate, error count, and avg latency.
    """
    _require_admin(current_user)
    data = get_route_stats(repo.db)
    return _wrap(data)


@router.get("/timeseries")
def analytics_timeseries(
    hours: int = Query(
        default=24,
        ge=1,
        le=168,
        description="Look-back window in hours (1–168, i.e. up to 7 days).",
    ),
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """
    Return hourly AI query counts over the past N hours.

    Uses a Firestore created_at >= cutoff filter for efficient range reads.
    Returns a list of hourly buckets with query_count, cache_hits, error_count.
    """
    _require_admin(current_user)
    data = get_usage_timeseries(repo.db, hours=hours)
    return _wrap(data)


@router.post("/cache/invalidate")
def analytics_cache_invalidate(
    current_user: User = Depends(get_current_user),
):
    """
    Immediately clear the in-memory analytics result cache.

    Forces the next analytics request to re-read from Firestore.
    Useful after bulk data corrections or during development.
    """
    _require_admin(current_user)
    count = invalidate_analytics_cache()
    return _wrap({"cleared_entries": count, "message": "Analytics cache cleared."})
