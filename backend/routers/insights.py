"""
routers/insights.py
───────────────────
Actionable AI insights and optimization recommendations — admin-only.

All endpoints require ADMIN_USER_IDS and return the standard envelope:
    {"data": {...}, "meta": {"generated_at": "..."}}

Insights are derived from the ai_usage Firestore collection and are
cached in-memory for 90 seconds to avoid Firestore fan-out.

Recommendation priority levels
──────────────────────────────
  CRITICAL — immediate action required (p95 latency > 10 s, error rate > 20 %)
  WARNING  — address soon       (p95 latency > 3 s, error rate > 5 %, cache < 20 %)
  INFO     — consider improvement (cache < 40 %)

Auto-action flags (read-only, never modifies user data)
─────────────────────────────────────────────────────
  FLAG_ROUTE_SLOW          — p95 latency > 5 000 ms
  FLAG_ROUTE_HIGH_ERROR    — error rate > 10 %
  FLAG_ROUTE_LOW_CACHE     — cache hit rate < 20 %
  FLAG_ROUTE_TRENDING_UP   — recent hour count > 2× baseline
  FLAG_USER_HIGH_VOLUME    — user accounts for ≥ 10 % of all queries
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from repositories import ResearchRepository, get_research_repository
from repositories.research import User
from routers.auth import get_current_user
from services.insights_service import (
    detect_heavy_users,
    detect_high_error_rate,
    detect_low_cache_hit_rate,
    detect_slow_queries,
    detect_trending_routes,
    generate_recommendations,
    get_insights_summary,
    get_route_performance,
    invalidate_insights_cache,
)

router = APIRouter(prefix="/insights", tags=["insights"])


# ── Admin guard (same pattern as analytics.py) ───────────────────────────────────


def _load_admin_ids() -> set[str]:
    raw = os.getenv("ADMIN_USER_IDS", "").strip()
    return {uid.strip() for uid in raw.split(",") if uid.strip()}


def _require_admin(current_user: User) -> None:
    """Raise 403 if the user is not in ADMIN_USER_IDS."""
    admin_ids = _load_admin_ids()
    if not admin_ids:
        raise HTTPException(
            status_code=403,
            detail="Insights access is disabled. Set ADMIN_USER_IDS in backend/.env.",
        )
    user_id = str(getattr(current_user, "id", "") or "")
    if user_id not in admin_ids:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access insights.",
        )


# ── Response wrapper ─────────────────────────────────────────────────────────────


def _wrap(data: Any) -> Dict[str, Any]:
    return {
        "data": data,
        "meta": {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        },
    }


# ── Endpoints ───────────────────────────────────────────────────────────────────


@router.get("/summary")
def insights_summary(
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """
    High-level dashboard summary.

    Returns:
    - counts of critical/warning/info issues across all categories
    - top 3 most urgent issues
    - top 5 recommendations per category
    """
    _require_admin(current_user)
    data = get_insights_summary(repo.db)
    return _wrap(data)


@router.get("/performance")
def insights_performance(
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """
    Per-route performance analysis.

    For each route: query count, p95 latency, avg latency, error rate,
    cache hit rate, slow-query percentage, and auto-action flags.
    Sorted by severity (CRITICAL first) then by p95 descending.
    """
    _require_admin(current_user)
    data = get_route_performance(repo.db)
    return _wrap({"routes": data})


@router.get("/performance/slow-queries")
def insights_slow_queries(
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """
    All individual queries with response time > 2 000 ms.

    Each entry shows: user_id, route, response_time_ms, model, status,
    timestamp, and severity (WARNING / CRITICAL).
    """
    _require_admin(current_user)
    data = detect_slow_queries(repo.db)
    return _wrap({"slow_queries": data})


@router.get("/cache")
def insights_cache(
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """
    Cache efficiency analysis — routes where cache hit rate < 30 %.

    Each entry includes route, cache hit rate, query count, and
    actionable recommendations to improve caching.
    """
    _require_admin(current_user)
    data = detect_low_cache_hit_rate(repo.db)
    return _wrap({"low_cache_routes": data})


@router.get("/errors")
def insights_errors(
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """
    High-error routes where error rate ≥ 10 %.

    Each entry shows: route, error rate, query count, severity, and
    a recommendation for investigation.
    """
    _require_admin(current_user)
    data = detect_high_error_rate(repo.db)
    return _wrap({"high_error_routes": data})


@router.get("/users/heavy")
def insights_heavy_users(
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """
    Users accounting for ≥ 10 % of total platform query volume.

    Each entry shows: user_id, query count, fraction of total,
    error rate, cache hit rate, avg latency, severity, and a
    recommendation for quota or limit review.
    """
    _require_admin(current_user)
    data = detect_heavy_users(repo.db)
    return _wrap({"heavy_users": data})


@router.get("/trending")
def insights_trending(
    hours: int = Query(
        default=24,
        ge=1,
        le=168,
        description="Look-back window in hours (1–168).",
    ),
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """
    Routes with recent query volume significantly above baseline.

    Useful for spotting traffic spikes, viral usage, or potential abuse.
    A route is flagged when its recent hourly rate is > 2× the baseline.
    """
    _require_admin(current_user)
    data = detect_trending_routes(repo.db, hours=hours)
    return _wrap({"trending_routes": data})


@router.get("/recommendations")
def insights_recommendations(
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """
    Full recommendations report across all insight categories.

    Returns:
    - cache_optimization: routes with low cache hit rate + suggestions
    - performance_issues: per-route latency/error/flags summary
    - high_usage_users: heavy users with quota recommendations
    - error_alerts: routes with elevated error rates
    - trending_routes: traffic spikes in the last 24 h
    """
    _require_admin(current_user)
    data = generate_recommendations(repo.db)
    return _wrap(data)


@router.post("/cache/invalidate")
def insights_cache_invalidate(
    current_user: User = Depends(get_current_user),
):
    """
    Clear the in-memory insights cache (90-second TTL).

    Forces the next insights request to re-query Firestore.
    """
    _require_admin(current_user)
    count = invalidate_insights_cache()
    return _wrap(
        {
            "cleared_entries": count,
            "message": "Insights cache cleared. Next request will query Firestore.",
        }
    )
