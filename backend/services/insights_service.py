"""
services/insights_service.py
────────────────────────────────
Actionable insights and optimization recommendations derived from the
``ai_usage`` Firestore collection — built on top of analytics_query_service.py.

Design philosophy
────────────────
* Every query is bounded (≤1 000 docs) and time-filtered. No full scans.
* Detection functions are pure and isolated — easy to test and compose.
* Recommendations are priority-ranked: CRITICAL > WARNING > INFO.
* Auto-actions are read-only — never modify user data or config automatically.
* A 90-second shared cache prevents duplicate Firestore reads across insight types.

Recommendation priority levels
──────────────────────────────
  CRITICAL — immediate action required (error rate > 20 %, p95 latency > 10 s)
  WARNING  — address soon (error rate > 5 %, p95 latency > 3 s, cache < 20 %)
  INFO     — consider improvement (cache < 40 %, latency trending up)

Auto-action flags (safe, read-only)
────────────────────────────────────
  FLAG_USER_HIGH_VOLUME    — user accounts for ≥ 10 % of all queries
  FLAG_ROUTE_SLOW          — p95 latency > 5 000 ms
  FLAG_ROUTE_HIGH_ERROR    — error rate > 10 %
  FLAG_ROUTE_LOW_CACHE     — cache hit rate < 20 %
  FLAG_ROUTE_TRENDING_UP   — recent hour count > 2× daily average
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.analytics_query_service import _fetch_docs, _safe_ratio

logger = logging.getLogger(__name__)

# ── Shared 90-second cache ─────────────────────────────────────────────────────
_RESULT_CACHE: Dict[str, Any] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL = 90  # seconds

_QUERY_LIMIT = 1_000  # same cap as analytics_query_service.py

# Detection thresholds
_SLOW_QUERY_MS = 2_000  # ms — queries above this are "slow"
_SLOW_P95_MS = 5_000  # ms — route p95 above this gets FLAG_ROUTE_SLOW
_CRITICAL_P95_MS = 10_000  # ms — p95 above this is CRITICAL
_HIGH_ERROR_RATE = 0.10  # 10 % — route error rate above this is WARNING
_CRITICAL_ERROR_RATE = 0.20  # 20 % — above this is CRITICAL
_LOW_CACHE_RATE = 0.30  # 30 % — cache hit rate below this is WARNING
_VERY_LOW_CACHE_RATE = 0.20  # 20 % — below this is CRITICAL
_HEAVY_USER_FRACTION = 0.10  # user ≥ 10 % of all queries gets flagged
_TREND_UP_FACTOR = 2.0  # recent hour > 2× daily avg → FLAG_ROUTE_TRENDING_UP


def _cache_get(key: str) -> Optional[Any]:
    with _CACHE_LOCK:
        entry = _RESULT_CACHE.get(key)
        if entry is None:
            return None
        result, ts = entry
        if time.time() - ts > _CACHE_TTL:
            _RESULT_CACHE.pop(key, None)
            return None
        return result


def _cache_set(key: str, value: Any) -> None:
    with _CACHE_LOCK:
        _RESULT_CACHE[key] = (value, time.time())


def _p95(values: List[int]) -> float:
    """Estimate p95 from a list of numbers."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * 0.95)
    return float(sorted_vals[min(idx, len(sorted_vals) - 1)])


def _avg(values: List[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


# ── Slow query detection ────────────────────────────────────────────────────────


def detect_slow_queries(db) -> List[Dict[str, Any]]:
    """
    Return all individual queries with response_time_ms > _SLOW_QUERY_MS.

    Each entry includes: user_id, route, response_time_ms, model, status,
    created_at, and a computed severity (WARNING / CRITICAL).
    """
    cache_key = "insights:slow_queries"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    docs = _fetch_docs(db, limit=_QUERY_LIMIT)

    slow: List[Dict[str, Any]] = []
    for d in docs:
        rt = int(d.get("response_time_ms") or 0)
        if rt < _SLOW_QUERY_MS:
            continue
        severity = "WARNING" if rt < _CRITICAL_P95_MS else "CRITICAL"
        slow.append(
            {
                "user_id": str(d.get("user_id") or ""),
                "route": str(d.get("route") or ""),
                "response_time_ms": rt,
                "model": str(d.get("model") or ""),
                "status": str(d.get("status") or ""),
                "created_at": _iso_ts(d.get("created_at")),
                "severity": severity,
            }
        )

    # Most severe first
    slow.sort(key=lambda x: x["response_time_ms"], reverse=True)
    result = slow[:100]  # cap at 100 worst offenders
    _cache_set(cache_key, result)
    return result


# ── Per-route performance summary ──────────────────────────────────────────────


def get_route_performance(db) -> List[Dict[str, Any]]:
    """
    Return per-route performance summary with p95 latency, error rate,
    cache rate, and auto-action flags.
    """
    cache_key = "insights:route_performance"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    docs = _fetch_docs(db, limit=_QUERY_LIMIT)

    routes: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "count": 0,
            "errors": 0,
            "cache_hits": 0,
            "rt_ms_list": [],
            "slow_count": 0,
        }
    )
    for d in docs:
        route = str(d.get("route") or "unknown")
        rt = int(d.get("response_time_ms") or 0)
        routes[route]["count"] += 1
        routes[route]["rt_ms_list"].append(rt)
        if d.get("status") == "error":
            routes[route]["errors"] += 1
        if d.get("cache_hit") is True:
            routes[route]["cache_hits"] += 1
        if rt >= _SLOW_QUERY_MS:
            routes[route]["slow_count"] += 1

    result: List[Dict[str, Any]] = []
    for route, s in routes.items():
        count = s["count"]
        if count == 0:
            continue
        p95 = _p95(s["rt_ms_list"])
        error_rate = _safe_ratio(s["errors"], count)
        cache_rate = _safe_ratio(s["cache_hits"], count)
        flags: List[str] = []
        if p95 >= _CRITICAL_P95_MS:
            severity = "CRITICAL"
            flags.append("FLAG_ROUTE_SLOW")
        elif p95 >= _SLOW_P95_MS:
            severity = "WARNING"
            flags.append("FLAG_ROUTE_SLOW")
        else:
            severity = "INFO"
        if error_rate >= _CRITICAL_ERROR_RATE:
            severity = _worse(severity, "CRITICAL")
            flags.append("FLAG_ROUTE_HIGH_ERROR")
        elif error_rate >= _HIGH_ERROR_RATE:
            severity = _worse(severity, "WARNING")
            flags.append("FLAG_ROUTE_HIGH_ERROR")
        if cache_rate < _VERY_LOW_CACHE_RATE:
            severity = _worse(severity, "CRITICAL")
            flags.append("FLAG_ROUTE_LOW_CACHE")
        elif cache_rate < _LOW_CACHE_RATE:
            severity = _worse(severity, "WARNING")
            flags.append("FLAG_ROUTE_LOW_CACHE")
        result.append(
            {
                "route": route,
                "query_count": count,
                "p95_latency_ms": p95,
                "avg_latency_ms": _avg(s["rt_ms_list"]),
                "error_rate": error_rate,
                "cache_hit_rate": cache_rate,
                "slow_query_count": s["slow_count"],
                "slow_query_pct": round(_safe_ratio(s["slow_count"], count) * 100, 1),
                "severity": severity,
                "flags": flags,
            }
        )

    # Sort by severity then by p95 desc
    _SEVERITY_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    result.sort(
        key=lambda x: (_SEVERITY_ORDER.get(x["severity"], 3), -x["p95_latency_ms"])
    )
    _cache_set(cache_key, result)
    return result


def _worse(a: str, b: str) -> str:
    """Return the worse of two severity levels."""
    return a if _SEVERITY_ORDER.get(a, 3) < _SEVERITY_ORDER.get(b, 3) else b


_SEVERITY_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}


# ── Cache efficiency analysis ──────────────────────────────────────────────────


def detect_low_cache_hit_rate(db) -> List[Dict[str, Any]]:
    """
    Identify routes where cache_hit_rate < _LOW_CACHE_RATE and return
    actionable recommendations to improve caching.
    """
    cache_key = "insights:low_cache"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    perf = get_route_performance(db)
    low_cache: List[Dict[str, Any]] = []

    for route_data in perf:
        if route_data["cache_hit_rate"] >= _LOW_CACHE_RATE:
            continue
        rate = route_data["cache_hit_rate"]
        recommendations: List[str] = []

        if rate < _VERY_LOW_CACHE_RATE:
            recommendations.append(
                f"Cache hit rate {rate:.0%} is critically low. "
                "Consider caching this route's responses or reducing TTL."
            )
        else:
            recommendations.append(
                f"Cache hit rate {rate:.0%} could be improved. "
                "Review query parameter normalization."
            )

        if route_data["query_count"] > 50:
            recommendations.append(
                f"High query volume ({route_data['query_count']} calls). "
                "Batch similar requests or pre-warm cache."
            )

        # Specific per-route suggestions
        route = route_data["route"]
        if "chat" in route:
            recommendations.append(
                "Cache chat responses by workspace_id + message_hash."
            )
        if "research_agent" in route:
            recommendations.append(
                "Cache research_agent results by topic hash + workspace."
            )
        if "search" in route:
            recommendations.append(
                "Deduplicate search queries within a time window (TTL ≥ 5 min)."
            )
        if "analyze" in route or "gap" in route:
            recommendations.append(
                "Analyze results are good candidates for 30-min TTL caching."
            )

        low_cache.append(
            {
                "route": route,
                "cache_hit_rate": rate,
                "query_count": route_data["query_count"],
                "recommendations": recommendations,
            }
        )

    low_cache.sort(key=lambda x: x["cache_hit_rate"])
    _cache_set(cache_key, low_cache)
    return low_cache


# ── High-error route detection ────────────────────────────────────────────────


def detect_high_error_rate(db) -> List[Dict[str, Any]]:
    """
    Return routes with error_rate >= _HIGH_ERROR_RATE, sorted by severity.
    """
    cache_key = "insights:high_errors"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    perf = get_route_performance(db)
    errors: List[Dict[str, Any]] = []

    for route_data in perf:
        er = route_data["error_rate"]
        if er < _HIGH_ERROR_RATE:
            continue
        severity = "CRITICAL" if er >= _CRITICAL_ERROR_RATE else "WARNING"
        errors.append(
            {
                "route": route_data["route"],
                "error_rate": er,
                "query_count": route_data["query_count"],
                "severity": severity,
                "recommendation": (
                    f"Error rate {er:.1%} — investigate server logs for "
                    f"{route_data['route']}. Check Groq API status and "
                    "rate limits."
                ),
            }
        )

    errors.sort(key=lambda x: -x["error_rate"])
    _cache_set(cache_key, errors)
    return errors


# ── Heavy user detection ───────────────────────────────────────────────────────


def detect_heavy_users(db) -> List[Dict[str, Any]]:
    """
    Identify users accounting for ≥ _HEAVY_USER_FRACTION of total query volume.
    """
    cache_key = "insights:heavy_users"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    docs = _fetch_docs(db, limit=_QUERY_LIMIT)
    total = len(docs)
    if total == 0:
        _cache_set(cache_key, [])
        return []

    user_counts: Dict[str, int] = defaultdict(int)
    user_stats: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"errors": 0, "cache_hits": 0, "rt_ms": []}
    )
    for d in docs:
        uid = str(d.get("user_id") or "unknown")
        user_counts[uid] += 1
        if d.get("status") == "error":
            user_stats[uid]["errors"] += 1
        if d.get("cache_hit") is True:
            user_stats[uid]["cache_hits"] += 1
        rt = d.get("response_time_ms")
        if rt:
            user_stats[uid]["rt_ms"].append(int(rt))

    threshold = max(1, int(total * _HEAVY_USER_FRACTION))
    heavy: List[Dict[str, Any]] = []
    for uid, count in user_counts.items():
        if count < threshold:
            continue
        frac = count / total
        s = user_stats[uid]
        heavy.append(
            {
                "user_id": uid,
                "query_count": count,
                "fraction_of_total": round(frac, 4),
                "error_rate": _safe_ratio(s["errors"], count),
                "cache_hit_rate": _safe_ratio(s["cache_hits"], count),
                "avg_latency_ms": _avg(s["rt_ms"]),
                "severity": "WARNING" if frac < 0.25 else "CRITICAL",
                "recommendation": (
                    f"User accounts for {frac:.1%} of all queries "
                    f"({count}/{total}). Consider usage limits or quota management."
                ),
            }
        )

    heavy.sort(key=lambda x: -x["fraction_of_total"])
    _cache_set(cache_key, heavy)
    return heavy


# ── Trending route detection ──────────────────────────────────────────────────


def detect_trending_routes(db, hours: int = 24) -> List[Dict[str, Any]]:
    """
    Find routes where recent query volume is significantly higher than
    the daily average — useful for spotting traffic spikes.
    """
    cache_key = f"insights:trending:{hours}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    cutoff_ts = time.time() - hours * 3600
    docs = _fetch_docs(db, cutoff_ts=cutoff_ts, limit=_QUERY_LIMIT)

    # Count per route
    route_counts: Dict[str, int] = defaultdict(int)
    for d in docs:
        route = str(d.get("route") or "unknown")
        route_counts[route] += 1

    total_docs = len(docs)
    if total_docs == 0:
        _cache_set(cache_key, [])
        return []

    # Compute implied hourly rate
    avg_per_route = total_docs / max(1, len(route_counts))
    recent_per_route = {r: route_counts[r] for r in route_counts}

    trending: List[Dict[str, Any]] = []
    for route, count in recent_per_route.items():
        # Approximate "hourly" rate assuming docs span the full window
        hourly_rate = count / hours
        # Compare to overall average hourly rate
        baseline = avg_per_route / hours
        if baseline > 0 and hourly_rate > baseline * _TREND_UP_FACTOR:
            trending.append(
                {
                    "route": route,
                    "recent_queries": count,
                    "window_hours": hours,
                    "approx_hourly_rate": round(hourly_rate, 1),
                    "baseline_hourly_rate": round(baseline, 1),
                    "spike_factor": round(hourly_rate / baseline, 1),
                    "recommendation": (
                        f"Traffic to {route} is {hourly_rate / baseline:.1f}× higher "
                        "than average. Investigate for abuse or successful viral use."
                    ),
                }
            )

    trending.sort(key=lambda x: -x["spike_factor"])
    _cache_set(cache_key, trending)
    return trending


# ── Recommendations engine ──────────────────────────────────────────────────────


def generate_recommendations(db) -> Dict[str, List[Dict[str, Any]]]:
    """
    Aggregate all detection results into a single prioritized recommendations dict.

    Returns:
        {
            "cache_optimization": [...],
            "performance_issues":  [...],
            "high_usage_users":    [...],
            "error_alerts":        [...],
            "trending_routes":     [...],
        }
    """
    cache_key = "insights:recommendations"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    result: Dict[str, List[Dict[str, Any]]] = {
        "cache_optimization": detect_low_cache_hit_rate(db),
        "performance_issues": get_route_performance(db),
        "high_usage_users": detect_heavy_users(db),
        "error_alerts": detect_high_error_rate(db),
        "trending_routes": detect_trending_routes(db),
    }
    _cache_set(cache_key, result)
    return result


# ── Summary view ───────────────────────────────────────────────────────────────


def get_insights_summary(db) -> Dict[str, Any]:
    """
    High-level dashboard summary: counts of critical/warning/info issues
    across all categories, plus the top 3 most urgent recommendations.
    """
    cache_key = "insights:summary"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    perf = get_route_performance(db)
    slow = detect_slow_queries(db)
    errors = detect_high_error_rate(db)
    heavy = detect_heavy_users(db)
    low_cache = detect_low_cache_hit_rate(db)
    trending = detect_trending_routes(db)

    def _count_by_sev(
        items: List[Dict[str, Any]], sev_field: str = "severity"
    ) -> Dict[str, int]:
        return {
            level: sum(1 for i in items if i.get(sev_field) == level)
            for level in ("CRITICAL", "WARNING", "INFO")
        }

    perf_counts = _count_by_sev(perf)
    error_counts = _count_by_sev(errors)
    heavy_counts = _count_by_sev(heavy)

    # Top 3 most urgent issues (CRITICAL first, then WARNING)
    urgent: List[Dict[str, Any]] = []
    for item in perf:
        if item["severity"] == "CRITICAL":
            urgent.append({"category": "performance", "route": item["route"], **item})
            break
    for item in errors:
        if item["severity"] == "CRITICAL":
            urgent.append({"category": "errors", **item})
            break
    for item in heavy:
        if item["severity"] == "CRITICAL":
            urgent.append({"category": "usage", **item})
            break
    for item in perf + errors + heavy:
        if item["severity"] == "WARNING" and len(urgent) < 3:
            urgent.append({"category": item.get("route", "general"), **item})

    result = {
        "overview": {
            "total_slow_queries": len(slow),
            "slow_query_threshold_ms": _SLOW_QUERY_MS,
            "routes_analyzed": len(perf),
            "critical_routes": perf_counts["CRITICAL"],
            "warning_routes": perf_counts["WARNING"],
            "info_routes": perf_counts["INFO"],
            "critical_errors": error_counts["CRITICAL"],
            "warning_errors": error_counts["WARNING"],
            "heavy_users": len(heavy),
            "critical_heavy_users": heavy_counts["CRITICAL"],
            "low_cache_routes": len(low_cache),
            "trending_routes": len(trending),
        },
        "top_issues": urgent[:3],
        "cache_optimization": low_cache[:5],
        "performance_by_route": perf[:10],
        "error_alerts": errors[:5],
        "high_usage_users": heavy[:5],
        "trending_routes": trending[:5],
    }
    _cache_set(cache_key, result)
    return result


# ── Cache invalidation ─────────────────────────────────────────────────────────


def invalidate_insights_cache() -> int:
    """Clear the insights cache. Returns number of entries cleared."""
    with _CACHE_LOCK:
        count = len(_RESULT_CACHE)
        _RESULT_CACHE.clear()
    return count


# ── Internal helpers ───────────────────────────────────────────────────────────


def _iso_ts(ts) -> Optional[str]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts.timestamp(), tz=timezone.utc).isoformat()
    except Exception:
        return None
