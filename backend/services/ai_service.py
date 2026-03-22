"""
services/ai_service.py
───────────────────────
Central AI call orchestration: two-tier cache → Groq → analytics → return.

Call flow
─────────
    ┌─────────────────────────────────────────────────────────┐
    │  run_ai_query(...)                                      │
    │                                                         │
    │  1. Normalize query → generate cache key                │
    │  2. L1 check  (in-memory, ~0 ms)                        │
    │     └── HIT → log analytics, return (layer="memory")   │
    │  3. L2 check  (Firestore, ~10–30 ms)                    │
    │     └── HIT → backfill L1, log, return (layer="firestore") │
    │  4. MISS → call Groq with Windows-compatible timeout    │
    │  5. On success → write L1 + L2, log analytics           │
    │  6. Return response dict                                 │
    └─────────────────────────────────────────────────────────┘

For routes that must NOT be cached (e.g. ``chat``), pass ``cacheable=False``;
usage is still logged via analytics.

Response dict keys (backward-compatible)
─────────────────────────────────────────
  response      (str)       — AI-generated text (empty string on error)
  cache_hit     (bool)      — True when served from any cache layer
  cache_layer   (str|None)  — "memory" | "firestore" | None (fresh Groq call)
  duration_ms   (int)       — wall-clock ms (0 on cache hit)
  model         (str)       — model name used
  error         (str|None)  — error message if status is "error"

Environment variables
─────────────────────
  AI_CALL_TIMEOUT_SECONDS      — hard timeout for Groq calls (default: 45)
  AI_CACHE_TTL_SECONDS         — Firestore cache TTL seconds (default: 3600)
  AI_MEMORY_CACHE_TTL_SECONDS  — In-memory cache TTL seconds (default: 30)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, Optional

from services.analytics_service import log_ai_usage
from services.cache_service import (
    UNCACHEABLE_ROUTES,
    generate_cache_key,
    get_cached_response,
    get_memory_cache,
    set_cached_response,
    set_memory_cache,
)

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = max(10, int(os.getenv("AI_CALL_TIMEOUT_SECONDS", "45") or 45))


def run_ai_query(
    *,
    groq_client: Any,
    db: Any,
    user_id: str,
    query: str,
    system_prompt: str,
    route: str,
    model_kwargs: Dict[str, Any],
    cacheable: bool = True,
    timeout_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute an AI query with two-tier cache, timeout guard, and analytics.

    Args:
        groq_client:     Groq client instance (from ``utils.groq_client``).
        db:              Firestore client (``repo.db``).
        user_id:         Authenticated user's ID as a string.
        query:           The user-facing query / prompt text sent to the LLM.
        system_prompt:   System prompt prepended to the conversation.
        route:           Logical identifier for this AI call (e.g. ``"analyze"``).
                         Used in analytics and cache routing.
        model_kwargs:    Dict of kwargs forwarded to
                         ``groq_client.chat.completions.create()``
                         (model, temperature, max_tokens, top_p …).
        cacheable:       Whether the response may be cached. Set to ``False``
                         for workspace-context-sensitive routes like ``"chat"``.
        timeout_seconds: Per-call timeout. Defaults to ``AI_CALL_TIMEOUT_SECONDS``
                         (45 s).

    Returns:
        Dict with keys:
          ``response``    (str)       AI-generated text (empty on error)
          ``cache_hit``   (bool)      True when served from any cache layer
          ``cache_layer`` (str|None)  "memory" | "firestore" | None
          ``duration_ms`` (int)       wall-clock ms (0 on cache hit)
          ``model``       (str)       model name used
          ``error``       (str|None)  error detail if status is "error"
    """
    timeout = int(timeout_seconds or _DEFAULT_TIMEOUT)
    effective_cacheable = cacheable and route not in UNCACHEABLE_ROUTES
    model_name = str(model_kwargs.get("model") or "")

    # ── 1. Generate cache key ────────────────────────────────────────────────
    cache_key: Optional[str] = None
    if effective_cacheable:
        cache_key = generate_cache_key(user_id=user_id, query=query)

    # ── 2. L1: In-memory cache check (~0 ms) ────────────────────────────────
    if cache_key:
        mem_hit = get_memory_cache(cache_key)
        if mem_hit:
            log_ai_usage(
                db,
                user_id=user_id,
                route=route,
                input_size=len(query),
                output_size=len(mem_hit),
                duration_ms=0,
                status="cache_hit",
                model=model_name,
                cache_hit=True,
            )
            logger.info(
                '{"event":"ai_query","route":"%s","user_id":"%s",'
                '"cache_hit":true,"cache_layer":"memory","duration_ms":0}',
                route,
                user_id,
            )
            return {
                "response": mem_hit,
                "cache_hit": True,
                "cache_layer": "memory",
                "duration_ms": 0,
                "model": model_name,
                "error": None,
            }

    # ── 3. L2: Firestore cache check (~10-30 ms) ─────────────────────────────
    if cache_key:
        fs_hit = get_cached_response(db, cache_key)
        if fs_hit:
            # Backfill L1 so the next request pays zero latency
            set_memory_cache(cache_key, fs_hit)
            log_ai_usage(
                db,
                user_id=user_id,
                route=route,
                input_size=len(query),
                output_size=len(fs_hit),
                duration_ms=0,
                status="cache_hit",
                model=model_name,
                cache_hit=True,
            )
            logger.info(
                '{"event":"ai_query","route":"%s","user_id":"%s",'
                '"cache_hit":true,"cache_layer":"firestore","duration_ms":0}',
                route,
                user_id,
            )
            return {
                "response": fs_hit,
                "cache_hit": True,
                "cache_layer": "firestore",
                "duration_ms": 0,
                "model": model_name,
                "error": None,
            }

    # ── 4. MISS: Groq call with Windows-compatible timeout guard ────────────
    start_ms = time.monotonic()
    response_text = ""
    status = "success"
    error_msg: Optional[str] = None

    try:
        _result_holder: Dict[str, Any] = {}
        _error_holder: Dict[str, Any] = {}

        def _call() -> None:
            try:
                resp = groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query[:32000]},
                    ],
                    **model_kwargs,
                )
                _result_holder["text"] = str(
                    (resp.choices[0].message.content or "")
                ).strip()
                _result_holder["model"] = str(
                    getattr(resp, "model", model_kwargs.get("model") or "")
                )
            except Exception as exc:
                _error_holder["exc"] = exc

        thread = threading.Thread(target=_call, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            status = "error"
            error_msg = f"AI call timed out after {timeout}s"
            logger.warning(
                '{"event":"ai_query_timeout","route":"%s","user_id":"%s",'
                '"timeout_s":%d}',
                route,
                user_id,
                timeout,
            )
        elif "exc" in _error_holder:
            raise _error_holder["exc"]
        else:
            response_text = _result_holder.get("text", "")
            model_name = _result_holder.get("model", model_name)

    except Exception as exc:
        status = "error"
        error_msg = str(exc)[:300]
        logger.warning(
            '{"event":"ai_query_error","route":"%s","user_id":"%s","error":"%s"}',
            route,
            user_id,
            error_msg,
        )

    duration_ms = max(0, int((time.monotonic() - start_ms) * 1000))

    # ── 5. Analytics (fire-and-forget, non-blocking) ─────────────────────────
    log_ai_usage(
        db,
        user_id=user_id,
        route=route,
        input_size=len(query),
        output_size=len(response_text),
        duration_ms=duration_ms,
        status=status,
        model=model_name,
        cache_hit=False,
    )
    logger.info(
        '{"event":"ai_query","route":"%s","user_id":"%s",'
        '"cache_hit":false,"cache_layer":null,"duration_ms":%d,"status":"%s"}',
        route,
        user_id,
        duration_ms,
        status,
    )

    # ── 6. Populate L2 (Firestore) + L1 (memory) on success ─────────────────
    if status == "success" and response_text and effective_cacheable and cache_key:
        # set_cached_response internally calls set_memory_cache too
        set_cached_response(
            db,
            cache_key,
            response_text,
            route=route,
            user_id=user_id,
        )

    return {
        "response": response_text,
        "cache_hit": False,
        "cache_layer": None,
        "duration_ms": duration_ms,
        "model": model_name,
        "error": error_msg,
    }
