"""
services/analytics_query_service.py
─────────────────────────────────────
Aggregation and insights layer on top of the Firestore ``ai_usage`` collection.

This module provides read-only analytics functions that power the admin
dashboard. All queries are bounded (max 1 000 docs per call) and results are
cached in a lightweight in-memory dict for 60 seconds to avoid hammering
Firestore on every dashboard refresh.

Firestore schema queried (ai_usage/{auto_id})
──────────────────────────────────────────────
  user_id          : str
  route            : str
  input_size       : int
  output_size      : int
  response_time_ms : int
  status           : str   ("success" | "error" | "cache_hit")
  model            : str
  cache_hit        : bool
  created_at       : Timestamp

Design notes
────────────
* Firestore has no native GROUP BY — aggregation is done in Python over the
  fetched page of documents. Queries are always bounded via `.limit()`.
* Results are cached in ``_RESULT_CACHE`` for ``_CACHE_TTL`` seconds so that
  repeated dashboard refreshes don't fan out dozens of Firestore reads.
* All functions gracefully return safe empty/zero defaults on any Firestore
  error to prevent analytics failures from surfacing as 5xx responses.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Result cache ─────────────────────────────────────────────────────────────
# Format: {cache_key: (result, inserted_ts)}
_RESULT_CACHE: Dict[str, Any] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL = 60  # seconds — all analytics results are cached for 1 minute

# Maximum documents fetched per Firestore query (keeps costs and latency low)
_QUERY_LIMIT = 1_000


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


def _ts_to_iso(ts) -> Optional[str]:
    """Convert a Firestore Timestamp to ISO-8601 string, or None on failure."""
    if ts is None:
        return None
    try:
        dt = datetime.fromtimestamp(ts.timestamp(), tz=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None


def _safe_ratio(numerator: int, denominator: int, decimals: int = 4) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, decimals)


# ── Core query helper ─────────────────────────────────────────────────────────

def _fetch_docs(
    db,
    *,
    user_id: Optional[str] = None,
    cutoff_ts: Optional[float] = None,
    limit: int = _QUERY_LIMIT,
) -> List[Dict[str, Any]]:
    """Fetch bounded ai_usage documents from Firestore.

    Applies optional filters for user_id and a created_at cutoff timestamp.
    Always applies .limit() so queries never do full collection scans.
    """
    try:
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore

        coll = db.collection("ai_usage")

        if cutoff_ts is not None:
            from datetime import datetime, timezone as _tz  # noqa: F811
            cutoff_dt = datetime.fromtimestamp(cutoff_ts, tz=_tz.utc)
            try:
                query = coll.where(
                    filter=FieldFilter("created_at", ">=", cutoff_dt)
                ).limit(min(limit, _QUERY_LIMIT))
            except Exception:
                query = coll.where(
                    "created_at", ">=", cutoff_dt
                ).limit(min(limit, _QUERY_LIMIT))
        else:
            query = coll.order_by(
                "created_at", direction="DESCENDING"
            ).limit(min(limit, _QUERY_LIMIT))

        docs = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            if user_id and str(data.get("user_id", "")) != str(user_id):
                continue
            docs.append(data)

        return docs
    except Exception as exc:  # pragma: no cover
        logger.warning("analytics_query_service: _fetch_docs failed: %s", exc)
        return []


# ── Public analytics functions ────────────────────────────────────────────────

def get_user_usage(db, user_id: str) -> Dict[str, Any]:
    """Return aggregated AI usage stats for a single user.

    Args:
        db:      Firestore client.
        user_id: User ID to aggregate for.

    Returns:
        Dict with keys:
          user_id, total_queries, successful_queries, error_count,
          cache_hits, cache_hit_rate, avg_response_time_ms,
          total_input_chars, total_output_chars, routes_used
    """
    cache_key = f"user_usage:{user_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    docs = _fetch_docs(db, user_id=user_id)

    total = len(docs)
    successes = sum(1 for d in docs if d.get("status") == "success")
    errors = sum(1 for d in docs if d.get("status") == "error")
    cache_hits = sum(1 for d in docs if d.get("cache_hit") is True)
    rt_ms = [int(d.get("response_time_ms", 0)) for d in docs if d.get("response_time_ms")]
    routes: Dict[str, int] = defaultdict(int)
    for d in docs:
        route = str(d.get("route") or "unknown")
        routes[route] += 1

    result: Dict[str, Any] = {
        "user_id": user_id,
        "total_queries": total,
        "successful_queries": successes,
        "error_count": errors,
        "cache_hits": cache_hits,
        "cache_hit_rate": _safe_ratio(cache_hits, total),
        "avg_response_time_ms": round(sum(rt_ms) / len(rt_ms), 1) if rt_ms else 0,
        "total_input_chars": sum(int(d.get("input_size", 0)) for d in docs),
        "total_output_chars": sum(int(d.get("output_size", 0)) for d in docs),
        "routes_used": dict(routes),
    }
    _cache_set(cache_key, result)
    return result


def get_global_stats(db) -> Dict[str, Any]:
    """Return platform-wide AI usage statistics.

    Reads the most recent _QUERY_LIMIT documents across all users.

    Returns:
        Dict with keys:
          total_queries, successful_queries, error_count, error_rate,
          cache_hits, cache_hit_rate, avg_response_time_ms,
          unique_users, docs_scanned
    """
    cache_key = "global_stats"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    docs = _fetch_docs(db)

    total = len(docs)
    successes = sum(1 for d in docs if d.get("status") == "success")
    errors = sum(1 for d in docs if d.get("status") == "error")
    cache_hits = sum(1 for d in docs if d.get("cache_hit") is True)
    rt_ms = [int(d.get("response_time_ms", 0)) for d in docs if d.get("response_time_ms")]
    unique_users = len({str(d.get("user_id", "")) for d in docs if d.get("user_id")})

    result: Dict[str, Any] = {
        "total_queries": total,
        "successful_queries": successes,
        "error_count": errors,
        "error_rate": _safe_ratio(errors, total),
        "cache_hits": cache_hits,
        "cache_hit_rate": _safe_ratio(cache_hits, total),
        "avg_response_time_ms": round(sum(rt_ms) / len(rt_ms), 1) if rt_ms else 0,
        "unique_users": unique_users,
        "docs_scanned": total,
    }
    _cache_set(cache_key, result)
    return result


def get_top_users(db, limit: int = 10) -> List[Dict[str, Any]]:
    """Return the top N users by total query count.

    Args:
        db:    Firestore client.
        limit: Number of top users to return (capped at 100).

    Returns:
        List of dicts sorted descending by total_queries:
          [{user_id, total_queries, cache_hits, cache_hit_rate,
            avg_response_time_ms, error_count}]
    """
    limit = max(1, min(int(limit), 100))
    cache_key = f"top_users:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    docs = _fetch_docs(db)

    # Aggregate per user in Python
    user_stats: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"total": 0, "cache_hits": 0, "errors": 0, "rt_ms": []}
    )
    for d in docs:
        uid = str(d.get("user_id") or "unknown")
        user_stats[uid]["total"] += 1
        if d.get("cache_hit"):
            user_stats[uid]["cache_hits"] += 1
        if d.get("status") == "error":
            user_stats[uid]["errors"] += 1
        rt = d.get("response_time_ms")
        if rt:
            user_stats[uid]["rt_ms"].append(int(rt))

    ranked = []
    for uid, s in user_stats.items():
        rt_list = s["rt_ms"]
        ranked.append(
            {
                "user_id": uid,
                "total_queries": s["total"],
                "cache_hits": s["cache_hits"],
                "cache_hit_rate": _safe_ratio(s["cache_hits"], s["total"]),
                "avg_response_time_ms": round(sum(rt_list) / len(rt_list), 1)
                if rt_list
                else 0,
                "error_count": s["errors"],
            }
        )

    ranked.sort(key=lambda x: x["total_queries"], reverse=True)
    result = ranked[:limit]
    _cache_set(cache_key, result)
    return result


def get_route_stats(db) -> Dict[str, Any]:
    """Return usage breakdown per logical route.

    Returns:
        Dict of route → {count, cache_hits, cache_hit_rate, error_count,
                          avg_response_time_ms}
    """
    cache_key = "route_stats"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    docs = _fetch_docs(db)

    routes: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "cache_hits": 0, "errors": 0, "rt_ms": []}
    )
    for d in docs:
        route = str(d.get("route") or "unknown")
        routes[route]["count"] += 1
        if d.get("cache_hit"):
            routes[route]["cache_hits"] += 1
        if d.get("status") == "error":
            routes[route]["errors"] += 1
        rt = d.get("response_time_ms")
        if rt:
            routes[route]["rt_ms"].append(int(rt))

    result: Dict[str, Any] = {}
    for route, s in sorted(routes.items(), key=lambda x: x[1]["count"], reverse=True):
        rt_list = s["rt_ms"]
        result[route] = {
            "count": s["count"],
            "cache_hits": s["cache_hits"],
            "cache_hit_rate": _safe_ratio(s["cache_hits"], s["count"]),
            "error_count": s["errors"],
            "avg_response_time_ms": round(sum(rt_list) / len(rt_list), 1)
            if rt_list
            else 0,
        }

    _cache_set(cache_key, result)
    return result


def get_usage_timeseries(db, hours: int = 24) -> List[Dict[str, Any]]:
    """Return hourly query counts over the past N hours.

    Uses a created_at >= cutoff filter so only the relevant time window is
    scanned (no full collection reads).

    Args:
        db:    Firestore client.
        hours: Look-back window in hours (1–168, i.e. up to 7 days).

    Returns:
        List of hourly buckets sorted ascending by hour:
          [{hour: "2026-03-22T10:00:00+00:00", query_count, cache_hits,
             error_count}]
    """
    hours = max(1, min(int(hours), 168))
    cache_key = f"timeseries:{hours}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    cutoff_ts = time.time() - hours * 3600
    docs = _fetch_docs(db, cutoff_ts=cutoff_ts, limit=_QUERY_LIMIT)

    # Bucket by hour (UTC)
    buckets: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"query_count": 0, "cache_hits": 0, "error_count": 0}
    )
    for d in docs:
        ts = d.get("created_at")
        if ts is None:
            continue
        try:
            dt = datetime.fromtimestamp(ts.timestamp(), tz=timezone.utc)
            # Truncate to the hour
            hour_key = dt.replace(minute=0, second=0, microsecond=0).isoformat()
            buckets[hour_key]["query_count"] += 1
            if d.get("cache_hit"):
                buckets[hour_key]["cache_hits"] += 1
            if d.get("status") == "error":
                buckets[hour_key]["error_count"] += 1
        except Exception:
            continue

    series = [
        {"hour": hour, **counts}
        for hour, counts in sorted(buckets.items())
    ]
    _cache_set(cache_key, series)
    return series


def invalidate_analytics_cache() -> int:
    """Clear all cached analytics results. Returns number of entries cleared."""
    with _CACHE_LOCK:
        count = len(_RESULT_CACHE)
        _RESULT_CACHE.clear()
    return count
