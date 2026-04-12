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
import json
import re
import hashlib
import random
from typing import Any, Dict, List, Optional

from services.analytics_service import log_ai_usage
from services.cache_service import (
    UNCACHEABLE_ROUTES,
    generate_cache_key,
    get_cached_response,
    get_memory_cache,
    set_cached_response,
    set_memory_cache,
)
from utils.groq_client import model_config

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int, *, minimum: int | None = None) -> int:
    raw = os.getenv(name, "")
    try:
        value = int(str(raw).strip() or default)
    except Exception:
        logger.warning("Invalid %s=%r; using default %s.", name, raw, default)
        value = int(default)
    if minimum is not None and value < minimum:
        return int(minimum)
    return value


def _env_float(name: str, default: float, *, minimum: float | None = None) -> float:
    raw = os.getenv(name, "")
    try:
        value = float(str(raw).strip() or default)
    except Exception:
        logger.warning("Invalid %s=%r; using default %s.", name, raw, default)
        value = float(default)
    if minimum is not None and value < minimum:
        return float(minimum)
    return value


_DEFAULT_TIMEOUT = _env_int("AI_CALL_TIMEOUT_SECONDS", 45, minimum=10)
_MAX_AI_CALL_RETRIES = _env_int("AI_CALL_MAX_RETRIES", 3, minimum=1)
_AI_RETRY_BASE_DELAY_SECONDS = _env_float(
    "AI_CALL_RETRY_BASE_DELAY_SECONDS", 0.25, minimum=0.05
)
_AI_RETRY_MAX_DELAY_SECONDS = max(
    _AI_RETRY_BASE_DELAY_SECONDS,
    _env_float("AI_CALL_RETRY_MAX_DELAY_SECONDS", 2.0),
)
_DECOMMISSION_FALLBACK_MODEL = str(
    os.getenv("GROQ_FALLBACK_MODEL") or "llama-3.3-70b-versatile"
).strip()
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", re.DOTALL | re.IGNORECASE)

TASK_CONFIGS: Dict[str, Dict[str, Any]] = {
    "paper_check": {
        "route": "paper_check",
        "task_slot": "pipeline",
        "longform": True,
        "temperature": 0.12,
        "max_tokens": 3200,
        "timeout_seconds": _env_int("AI_PAPER_CHECK_TIMEOUT_SECONDS", 55, minimum=15),
        "cacheable": True,
    },
    "ai_writing_detection": {
        "route": "ai_writing_detection",
        "task_slot": "pipeline",
        "longform": False,
        "temperature": 0.08,
        "max_tokens": 1800,
        "timeout_seconds": _env_int(
            "AI_WRITING_DETECTION_TIMEOUT_SECONDS", 35, minimum=12
        ),
        "cacheable": True,
    },
    "research_report": {
        "route": "research_report",
        "task_slot": "pipeline",
        "longform": True,
        "temperature": 0.25,
        "max_tokens": 6000,
        "timeout_seconds": _env_int(
            "AI_RESEARCH_REPORT_TIMEOUT_SECONDS", 120, minimum=30
        ),
        "cacheable": True,
    },
    "compare_papers": {
        "route": "compare_papers",
        "task_slot": "pipeline",
        "longform": True,
        "temperature": 0.2,
        "max_tokens": 4000,
        "timeout_seconds": _env_int(
            "AI_COMPARE_PAPERS_TIMEOUT_SECONDS", 60, minimum=20
        ),
        "cacheable": True,
    },
    "workspace_insights": {
        "route": "workspace_insights",
        "task_slot": "pipeline",
        "longform": True,
        "temperature": 0.12,
        "max_tokens": 3600,
        "timeout_seconds": _env_int(
            "AI_WORKSPACE_INSIGHTS_TIMEOUT_SECONDS", 90, minimum=20
        ),
        "cacheable": False,
    },
    "workspace_feed": {
        "route": "workspace_feed",
        "task_slot": "pipeline",
        "longform": True,
        "temperature": 0.12,
        "max_tokens": 2600,
        "timeout_seconds": _env_int(
            "AI_WORKSPACE_FEED_TIMEOUT_SECONDS", 90, minimum=20
        ),
        "cacheable": False,
    },
    "explain_paper": {
        "route": "explain_paper",
        "task_slot": "pipeline",
        "longform": True,
        "temperature": 0.1,
        "max_tokens": 2400,
        "timeout_seconds": _env_int(
            "AI_EXPLAIN_PAPER_TIMEOUT_SECONDS", 60, minimum=20
        ),
        "cacheable": True,
    },
}


def _is_model_decommissioned_error(message: str) -> bool:
    lowered = str(message or "").lower()
    return "model_decommissioned" in lowered or (
        "decommissioned" in lowered and "model" in lowered
    )


def _is_retryable_ai_exception(exc: Exception) -> bool:
    message = str(exc or "").lower()
    retry_markers = (
        "timeout",
        "timed out",
        "temporar",
        "rate limit",
        "429",
        "too many requests",
        "connection reset",
        "service unavailable",
        "503",
        "502",
        "504",
    )
    return any(marker in message for marker in retry_markers)


def _cache_scope(
    *,
    route: str,
    system_prompt: str,
    model_kwargs: Dict[str, Any],
) -> str:
    system_hash = hashlib.sha256(
        str(system_prompt or "").strip().encode("utf-8")
    ).hexdigest()[:12]
    scope_payload = {
        "route": str(route or ""),
        "model": str(model_kwargs.get("model") or ""),
        "temperature": model_kwargs.get("temperature"),
        "top_p": model_kwargs.get("top_p"),
        "system_hash": system_hash,
    }
    return json.dumps(scope_payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def call_chat_completion_with_retry(
    *,
    groq_client: Any,
    messages: List[Dict[str, str]],
    model_kwargs: Dict[str, Any],
    route: str,
    user_id: str = "",
    timeout_seconds: Optional[int] = None,
    max_attempts: Optional[int] = None,
) -> Dict[str, Any]:
    timeout = int(timeout_seconds or _DEFAULT_TIMEOUT)
    attempts = max(1, int(max_attempts or _MAX_AI_CALL_RETRIES))
    start_ms = time.monotonic()
    last_error: Optional[str] = None
    model_name = str(model_kwargs.get("model") or "")
    response_text = ""

    for attempt in range(1, attempts + 1):
        result_holder: Dict[str, Any] = {}
        error_holder: Dict[str, Any] = {}

        def _call() -> None:
            try:
                request_kwargs = dict(model_kwargs)
                requested_model = str(request_kwargs.get("model") or "")
                resp = groq_client.chat.completions.create(
                    messages=messages,
                    **request_kwargs,
                )
                result_holder["text"] = str(
                    (resp.choices[0].message.content or "")
                ).strip()
                result_holder["model"] = str(
                    getattr(resp, "model", request_kwargs.get("model") or "")
                )
            except Exception as exc:
                if (
                    _DECOMMISSION_FALLBACK_MODEL
                    and _is_model_decommissioned_error(str(exc))
                    and requested_model != _DECOMMISSION_FALLBACK_MODEL
                ):
                    logger.warning(
                        '{"event":"ai_model_fallback","route":"%s","from_model":"%s","to_model":"%s"}',
                        route,
                        requested_model,
                        _DECOMMISSION_FALLBACK_MODEL,
                    )
                    try:
                        fallback_kwargs = dict(request_kwargs)
                        fallback_kwargs["model"] = _DECOMMISSION_FALLBACK_MODEL
                        resp = groq_client.chat.completions.create(
                            messages=messages,
                            **fallback_kwargs,
                        )
                        result_holder["text"] = str(
                            (resp.choices[0].message.content or "")
                        ).strip()
                        result_holder["model"] = str(
                            getattr(resp, "model", fallback_kwargs.get("model") or "")
                        )
                        return
                    except Exception as fallback_exc:
                        error_holder["exc"] = fallback_exc
                        return
                error_holder["exc"] = exc

        thread = threading.Thread(target=_call, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        timeout_error = None
        call_exc = error_holder.get("exc")
        if thread.is_alive():
            timeout_error = RuntimeError(f"AI call timed out after {timeout}s")
            last_error = str(timeout_error)
        elif call_exc is not None:
            last_error = str(call_exc)[:300]
        else:
            response_text = result_holder.get("text", "")
            model_name = result_holder.get("model", model_name)
            break

        retryable = bool(timeout_error) or (
            isinstance(call_exc, Exception) and _is_retryable_ai_exception(call_exc)
        )
        should_retry = attempt < attempts
        if (not retryable) or (not should_retry):
            break
        backoff = min(
            _AI_RETRY_MAX_DELAY_SECONDS,
            _AI_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)),
        ) + random.uniform(0.0, 0.05)
        logger.warning(
            '{"event":"ai_call_retry","route":"%s","user_id":"%s","attempt":%d,'
            '"max_attempts":%d,"backoff_s":%.3f,"error":"%s"}',
            route,
            user_id,
            attempt,
            attempts,
            backoff,
            str(last_error or "")[:160],
        )
        time.sleep(backoff)

    return {
        "response": response_text,
        "model": model_name,
        "error": None if response_text else (last_error or "AI call failed."),
        "duration_ms": max(0, int((time.monotonic() - start_ms) * 1000)),
    }


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
        cache_key = generate_cache_key(
            user_id=user_id,
            query=query,
            scope=_cache_scope(
                route=route,
                system_prompt=system_prompt,
                model_kwargs=model_kwargs,
            ),
        )

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
        attempt_errors = []
        for attempt in range(1, _MAX_AI_CALL_RETRIES + 1):
            _result_holder: Dict[str, Any] = {}
            _error_holder: Dict[str, Any] = {}

            def _call() -> None:
                try:
                    request_kwargs = dict(model_kwargs)
                    requested_model = str(request_kwargs.get("model") or "")
                    resp = groq_client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": query[:32000]},
                        ],
                        **request_kwargs,
                    )
                    _result_holder["text"] = str(
                        (resp.choices[0].message.content or "")
                    ).strip()
                    _result_holder["model"] = str(
                        getattr(resp, "model", request_kwargs.get("model") or "")
                    )
                except Exception as exc:
                    if (
                        _DECOMMISSION_FALLBACK_MODEL
                        and _is_model_decommissioned_error(str(exc))
                        and requested_model != _DECOMMISSION_FALLBACK_MODEL
                    ):
                        logger.warning(
                            '{"event":"ai_model_fallback","route":"%s","from_model":"%s","to_model":"%s"}',
                            route,
                            requested_model,
                            _DECOMMISSION_FALLBACK_MODEL,
                        )
                        try:
                            fallback_kwargs = dict(request_kwargs)
                            fallback_kwargs["model"] = _DECOMMISSION_FALLBACK_MODEL
                            resp = groq_client.chat.completions.create(
                                messages=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": query[:32000]},
                                ],
                                **fallback_kwargs,
                            )
                            _result_holder["text"] = str(
                                (resp.choices[0].message.content or "")
                            ).strip()
                            _result_holder["model"] = str(
                                getattr(resp, "model", fallback_kwargs.get("model") or "")
                            )
                            return
                        except Exception as fallback_exc:
                            _error_holder["exc"] = fallback_exc
                            return
                    _error_holder["exc"] = exc

            thread = threading.Thread(target=_call, daemon=True)
            thread.start()
            thread.join(timeout=timeout)

            timeout_error = None
            call_exc = _error_holder.get("exc")
            if thread.is_alive():
                timeout_error = RuntimeError(f"AI call timed out after {timeout}s")
                current_error = str(timeout_error)
                logger.warning(
                    '{"event":"ai_query_timeout","route":"%s","user_id":"%s",'
                    '"timeout_s":%d,"attempt":%d,"max_attempts":%d}',
                    route,
                    user_id,
                    timeout,
                    attempt,
                    _MAX_AI_CALL_RETRIES,
                )
            elif call_exc is not None:
                current_error = str(call_exc)[:300]
            else:
                response_text = _result_holder.get("text", "")
                model_name = _result_holder.get("model", model_name)
                break

            attempt_errors.append(current_error)
            should_retry = attempt < _MAX_AI_CALL_RETRIES
            retryable = bool(timeout_error) or (
                isinstance(call_exc, Exception) and _is_retryable_ai_exception(call_exc)
            )
            if (not should_retry) or (not retryable):
                if call_exc is not None and not retryable:
                    raise call_exc
                status = "error"
                error_msg = current_error
                break
            backoff = min(
                _AI_RETRY_MAX_DELAY_SECONDS,
                _AI_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)),
            ) + random.uniform(0.0, 0.05)
            logger.warning(
                '{"event":"ai_query_retry","route":"%s","user_id":"%s","attempt":%d,'
                '"max_attempts":%d,"backoff_s":%.3f,"error":"%s"}',
                route,
                user_id,
                attempt,
                _MAX_AI_CALL_RETRIES,
                backoff,
                current_error[:160],
            )
            time.sleep(backoff)

        if not response_text and status != "error" and attempt_errors:
            status = "error"
            error_msg = attempt_errors[-1]

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


def get_task_config(task_type: str, **overrides: Any) -> Dict[str, Any]:
    base = dict(TASK_CONFIGS.get(task_type) or {})
    if not base:
        raise ValueError(f"Unsupported AI task type '{task_type}'.")
    for key, value in overrides.items():
        if value is not None:
            base[key] = value
    return base


def _extract_json_payload(text: str) -> Any:
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("AI returned an empty response.")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = _JSON_BLOCK_RE.search(raw)
        if match:
            return json.loads(match.group(1))
        start_obj = raw.find("{")
        end_obj = raw.rfind("}")
        if start_obj != -1 and end_obj > start_obj:
            try:
                return json.loads(raw[start_obj : end_obj + 1])
            except json.JSONDecodeError:
                pass
        start_arr = raw.find("[")
        end_arr = raw.rfind("]")
        if start_arr != -1 and end_arr > start_arr:
            try:
                return json.loads(raw[start_arr : end_arr + 1])
            except json.JSONDecodeError:
                pass
        raise


def run_structured_json_task(
    *,
    groq_client: Any,
    db: Any,
    user_id: str,
    task_type: str,
    query: str,
    system_prompt: str,
    cacheable: Optional[bool] = None,
    timeout_seconds: Optional[int] = None,
    model_overrides: Optional[Dict[str, Any]] = None,
    max_attempts: int = 2,
) -> Dict[str, Any]:
    task_config = get_task_config(task_type)
    effective_cacheable = task_config.get("cacheable", True) if cacheable is None else bool(cacheable)
    effective_timeout = int(timeout_seconds or task_config.get("timeout_seconds") or _DEFAULT_TIMEOUT)
    model_kwargs = model_config(
        task=task_config.get("task_slot"),
        longform=bool(task_config.get("longform")),
        temperature=task_config.get("temperature"),
        max_tokens=task_config.get("max_tokens"),
        **(model_overrides or {}),
    )

    last_result: Dict[str, Any] = {}
    last_error: Optional[str] = None
    attempts = max(1, int(max_attempts or 1))

    for attempt in range(1, attempts + 1):
        result = run_ai_query(
            groq_client=groq_client,
            db=db,
            user_id=user_id,
            query=query,
            system_prompt=system_prompt,
            route=str(task_config.get("route") or task_type),
            model_kwargs=model_kwargs,
            cacheable=effective_cacheable,
            timeout_seconds=effective_timeout,
        )
        last_result = result
        if result.get("error") and not result.get("response"):
            last_error = str(result.get("error") or "AI task failed.")
            continue
        try:
            parsed = _extract_json_payload(str(result.get("response") or ""))
            return {
                **result,
                "parsed": parsed,
            }
        except Exception as exc:
            last_error = f"Structured AI output parsing failed: {str(exc)}"
            if attempt >= attempts:
                break

    return {
        **last_result,
        "parsed": None,
        "error": last_error or str(last_result.get("error") or "Structured AI task failed."),
    }


def compare_papers_task(
    *,
    groq_client: Any,
    db: Any,
    user_id: str,
    papers_context: str,
    optional_context: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a highly structured JSON comparison between multiple papers.
    Ensures strict JSON output matching the requested schema.
    """
    system_prompt = (
        "You are an expert academic research assistant tasked with comparing multiple research papers.\n"
        "Your goal is to provide a structured, side-by-side comparison based ONLY on the provided context.\n"
        "EXTREMELY IMPORTANT: DO NOT HALLUCINATE. If information is missing, state 'Not mentioned in provided text'.\n"
        "You MUST return the output strictly as a valid JSON object matching this schema exactly:\n"
        "{\n"
        '  "comparison": {\n'
        '    "key_contributions": [{"paper_id": "...", "contribution": "..."}],\n'
        '    "methodology_comparison": "Detailed comparison of methods...",\n'
        '    "strengths": {"paper_id_1": ["...", "..."], "paper_id_2": ["..."]},\n'
        '    "weaknesses": {"paper_id_1": ["...", "..."], "paper_id_2": ["..."]},\n'
        '    "evidence_quality": {"paper_id_1": "...", "paper_id_2": "..."},\n'
        '    "contradictions": ["Point of disagreement 1..."],\n'
        '    "summary": "Final synthesized summary of how these papers relate."\n'
        "  }\n"
        "}"
    )

    query = f"Compare the following papers:\n\n{papers_context}\n"
    if optional_context:
        query += f"\nUser's specific focus/context for comparison: {optional_context}\n"

    return run_structured_json_task(
        groq_client=groq_client,
        db=db,
        user_id=user_id,
        task_type="compare_papers",
        query=query,
        system_prompt=system_prompt,
        model_overrides={"response_format": {"type": "json_object"}},
    )

def generate_research_report_task(
    *,
    groq_client: Any,
    db: Any,
    user_id: str,
    context: str,
    topic: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a highly structured JSON multi-paper research report.
    """
    system_prompt = (
        "You are an expert academic research assistant producing a multi-paper research report.\n"
        "Synthesize (do not summarize paper-by-paper) and stay strictly grounded in the provided context.\n"
        "EXTREMELY IMPORTANT:\n"
        "- Do NOT hallucinate. If evidence is missing, explicitly say so.\n"
        "- Do NOT invent citations, datasets, metrics, or numeric results.\n"
        "- Prefer precise language: 'The provided text suggests...' and 'Insufficient evidence...' when needed.\n"
        "- Highlight trends (methods), consensus vs conflicts, and actionable research gaps.\n"
        "You MUST return the output strictly as a valid JSON object matching this schema exactly:\n"
        "{\n"
        '  "title": "Generated title of the report",\n'
        '  "abstract": "Executive summary...",\n'
        '  "key_themes": ["Theme 1", "Theme 2"],\n'
        '  "literature_overview": "Overview of the landscape...",\n'
        '  "methodology_trends": "Trends in methods...",\n'
        '  "consensus_findings": "What papers agree on...",\n'
        '  "conflicting_views": "Where the papers disagree...",\n'
        '  "research_gaps": ["Gap 1", "Gap 2"],\n'
        '  "future_directions": ["Direction 1", "Direction 2"],\n'
        '  "conclusion": "Final concluding remarks..."\n'
        "}"
    )

    query = "Synthesize the following research context into a report:\n\n"
    if topic:
        query += f"Focus Topic / Query: {topic}\n\n"
    query += f"Context:\n{context}\n"

    return run_structured_json_task(
        groq_client=groq_client,
        db=db,
        user_id=user_id,
        task_type="research_report",
        query=query,
        system_prompt=system_prompt,
        model_overrides={"response_format": {"type": "json_object"}},
        timeout_seconds=120,
    )
