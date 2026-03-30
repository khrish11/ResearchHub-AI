from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from repositories import ResearchRepository
from services.ai_service import run_ai_query
from services.cache_service import generate_cache_key, get_cached_response, get_memory_cache, set_cached_response
from services.paper_check_service import aggregate_and_compare_papers, aggregate_and_generate_report
from services.paper_explain_service import get_or_generate_paper_explanation
from services.rag_query_handler import RAGQueryInput
from services.rag_runtime import get_rag_runtime
from services.workspace_insights_service import get_or_generate_workspace_insights
from services.onboarding_service import (
    ONBOARDING_STEP_COMPARE,
    ONBOARDING_STEP_EXPLAIN,
    ONBOARDING_STEP_REPORT,
    mark_step_best_effort,
)
from utils.groq_client import client as groq_client, model_config


logger = logging.getLogger(__name__)

INTENT_EXPLAIN = "explain"
INTENT_COMPARE = "compare"
INTENT_REPORT = "report"
INTENT_RAG_QUERY = "rag_query"
INTENT_INSIGHTS = "insights"
SUPPORTED_INTENTS: Tuple[str, ...] = (
    INTENT_EXPLAIN,
    INTENT_COMPARE,
    INTENT_REPORT,
    INTENT_RAG_QUERY,
    INTENT_INSIGHTS,
)

_INTENT_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    INTENT_EXPLAIN: (
        "explain this paper",
        "explain paper",
        "what is this paper about",
        "key contribution",
        "method summary",
        "why it matters",
    ),
    INTENT_COMPARE: (
        "compare",
        "contrast",
        "vs",
        "versus",
        "differences between",
        "which paper is better",
    ),
    INTENT_REPORT: (
        "generate report",
        "research report",
        "write report",
        "report for",
        "create report",
        "brief",
    ),
    INTENT_INSIGHTS: (
        "main trends",
        "key trends",
        "emerging themes",
        "contradictions across",
        "research gaps",
        "insights",
        "next reads",
    ),
    INTENT_RAG_QUERY: (
        "summarize workspace",
        "summarize my workspace",
        "what does my workspace say",
        "tell me about",
        "what are",
        "how does",
        "why is",
    ),
}

_WORD_RE = re.compile(r"[a-z0-9']+")


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _normalize_query(text: str) -> str:
    return re.sub(r"\s+", " ", _safe_str(text).lower())


def _tokenize(text: str) -> List[str]:
    return _WORD_RE.findall(_normalize_query(text))


def _unique_ints(values: Sequence[Any]) -> List[int]:
    output: List[int] = []
    for value in values:
        num = _coerce_int(value, 0)
        if num > 0 and num not in output:
            output.append(num)
    return output


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _collect_sources_from_papers(
    *,
    repo: ResearchRepository,
    user_id: int,
    paper_ids: Sequence[int],
) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    for paper_id in _unique_ints(paper_ids):
        paper = repo.find_paper_for_user(int(paper_id), int(user_id))
        if paper is None:
            continue
        doi = _safe_str(getattr(paper, "doi", ""))
        url = _safe_str(getattr(paper, "url", ""))
        sources.append(
            {
                "source_id": f"paper:{int(paper.id)}",
                "source_type": "paper",
                "title": _safe_str(getattr(paper, "title", "")) or f"Paper {int(paper.id)}",
                "url": url or (f"https://doi.org/{doi}" if doi else ""),
                "doi": doi,
            }
        )
    return sources


def detect_copilot_intent(
    *,
    query: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    normalized = _normalize_query(query)
    tokens = set(_tokenize(normalized))
    context = context or {}
    paper_ids = _unique_ints(context.get("paper_ids") or [])
    workspace_id = _coerce_int(context.get("workspace_id"), 0)

    scores = {intent: 0.0 for intent in SUPPORTED_INTENTS}
    for intent, phrases in _INTENT_KEYWORDS.items():
        for phrase in phrases:
            phrase_norm = _normalize_query(phrase)
            if phrase_norm and phrase_norm in normalized:
                scores[intent] += 0.55
            phrase_tokens = set(_tokenize(phrase_norm))
            if phrase_tokens and phrase_tokens.issubset(tokens):
                scores[intent] += 0.2

    if "?" in normalized:
        scores[INTENT_RAG_QUERY] += 0.08
    if "trend" in tokens or "trends" in tokens:
        scores[INTENT_INSIGHTS] += 0.25
    if "report" in tokens:
        scores[INTENT_REPORT] += 0.3
    if "compare" in tokens:
        scores[INTENT_COMPARE] += 0.3
    if "explain" in tokens:
        scores[INTENT_EXPLAIN] += 0.3
    if "summarize" in tokens or "summary" in tokens:
        scores[INTENT_RAG_QUERY] += 0.2

    if len(paper_ids) == 1:
        scores[INTENT_EXPLAIN] += 0.18
    if len(paper_ids) >= 2:
        scores[INTENT_COMPARE] += 0.24
        scores[INTENT_REPORT] += 0.1
    if workspace_id > 0:
        scores[INTENT_INSIGHTS] += 0.08
        scores[INTENT_RAG_QUERY] += 0.08

    sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_intent, best_score = sorted_scores[0]
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0
    margin = best_score - second_score
    confidence = _clamp(0.35 + (best_score * 0.45) + (margin * 0.4))
    unclear = bool(best_score < 0.45 or margin < 0.08)
    intent = INTENT_RAG_QUERY if unclear else best_intent

    return {
        "intent": intent,
        "raw_intent": best_intent,
        "intent_confidence": round(confidence, 4),
        "scores": {key: round(val, 4) for key, val in scores.items()},
        "unclear": unclear,
    }


def _ensure_workspace_access(
    *,
    repo: ResearchRepository,
    workspace_id: Optional[int],
    user_id: int,
) -> Optional[int]:
    target = _coerce_int(workspace_id, 0)
    if target <= 0:
        return None
    workspace = repo.find_workspace_for_user(target, int(user_id))
    if workspace is None:
        raise ValueError("Workspace not found or inaccessible.")
    return target


def _resolve_context(
    *,
    repo: ResearchRepository,
    user_id: int,
    context: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    context = dict(context or {})
    workspace_id = _ensure_workspace_access(
        repo=repo,
        workspace_id=context.get("workspace_id"),
        user_id=user_id,
    )
    paper_ids = _unique_ints(context.get("paper_ids") or [])
    validated_paper_ids: List[int] = []
    inferred_workspace_id = workspace_id
    for paper_id in paper_ids:
        paper = repo.find_paper_for_user(int(paper_id), int(user_id))
        if paper is None:
            raise ValueError(f"Paper {paper_id} was not found or is not accessible.")
        paper_workspace_id = _coerce_int(getattr(paper, "workspace_id", 0), 0)
        if workspace_id and paper_workspace_id != int(workspace_id):
            raise ValueError("Provided paper_ids must belong to the same workspace_id.")
        inferred_workspace_id = inferred_workspace_id or paper_workspace_id
        validated_paper_ids.append(int(paper_id))
    return {
        "workspace_id": inferred_workspace_id,
        "paper_ids": validated_paper_ids,
    }


def _cache_key_for_request(
    *,
    user_id: int,
    query: str,
    context: Dict[str, Any],
) -> str:
    payload = {
        "q": _normalize_query(query),
        "workspace_id": _coerce_int(context.get("workspace_id"), 0),
        "paper_ids": _unique_ints(context.get("paper_ids") or []),
        "version": "copilot-v1",
    }
    return generate_cache_key(
        user_id=str(int(user_id)),
        query=f"copilot::{json.dumps(payload, sort_keys=True, ensure_ascii=True)}",
    )


def _parse_cached_payload(raw: str) -> Optional[Dict[str, Any]]:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


async def _route_explain(
    *,
    repo: ResearchRepository,
    user_id: int,
    query: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    paper_ids = _unique_ints(context.get("paper_ids") or [])
    workspace_id = _coerce_int(context.get("workspace_id"), 0)
    if not paper_ids and workspace_id > 0:
        workspace_papers = repo.list_papers_for_workspace(workspace_id)
        if len(workspace_papers) == 1:
            paper_ids = [int(workspace_papers[0].id)]
    if not paper_ids:
        raise ValueError("Explain intent requires at least one paper_id in context.")
    paper = repo.find_paper_for_user(paper_ids[0], int(user_id))
    if paper is None:
        raise ValueError("Requested paper was not found.")
    explain = await get_or_generate_paper_explanation(
        repo=repo,
        paper=paper,
        user_id=int(user_id),
        refresh=False,
        include_rag=True,
    )
    if workspace_id > 0:
        mark_step_best_effort(
            repo=repo,
            user_id=int(user_id),
            workspace_id=int(workspace_id),
            step_id=ONBOARDING_STEP_EXPLAIN,
        )
    sources = explain.get("sources") if isinstance(explain.get("sources"), list) else []
    confidence = 0.7 if _safe_str(explain.get("status")) == "fallback" else 0.84
    if sources:
        confidence = _clamp(confidence + min(0.12, len(sources) * 0.02))
    content = {
        "simple_explanation": _safe_str(explain.get("simple_explanation")),
        "key_points": explain.get("key_points") or [],
        "methodology": _safe_str(explain.get("methodology")),
        "strengths": explain.get("strengths") or [],
        "weaknesses": explain.get("weaknesses") or [],
        "evidence_quality": _safe_str(explain.get("evidence_quality")),
        "ai_likelihood": _safe_str(explain.get("ai_likelihood")),
        "significance": _safe_str(explain.get("significance")),
        "disclaimer": _safe_str(explain.get("disclaimer")),
    }
    return {
        "type": INTENT_EXPLAIN,
        "content": content,
        "sources": sources,
        "confidence": round(confidence, 4),
    }


async def _route_compare(
    *,
    repo: ResearchRepository,
    user_id: int,
    query: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    paper_ids = _unique_ints(context.get("paper_ids") or [])
    workspace_id = _coerce_int(context.get("workspace_id"), 0)
    if len(paper_ids) < 2 and workspace_id > 0:
        fallback_ids = [int(paper.id) for paper in repo.list_papers_for_workspace(workspace_id)]
        paper_ids = _unique_ints(fallback_ids)[:5]
    if len(paper_ids) < 2:
        raise ValueError("Compare intent requires at least two paper_ids.")
    compare_result = await asyncio.to_thread(
        aggregate_and_compare_papers,
        repo=repo,
        user_id=str(int(user_id)),
        paper_ids=paper_ids[:5],
        optional_context=query[:1000],
    )
    if workspace_id > 0:
        mark_step_best_effort(
            repo=repo,
            user_id=int(user_id),
            workspace_id=int(workspace_id),
            step_id=ONBOARDING_STEP_COMPARE,
        )
    sources = _collect_sources_from_papers(repo=repo, user_id=user_id, paper_ids=paper_ids)
    confidence = _clamp(0.66 + (0.04 * min(4, len(sources))))
    return {
        "type": INTENT_COMPARE,
        "content": compare_result if isinstance(compare_result, dict) else {"summary": _safe_str(compare_result)},
        "sources": sources,
        "confidence": round(confidence, 4),
    }


async def _route_report(
    *,
    repo: ResearchRepository,
    user_id: int,
    query: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    paper_ids = _unique_ints(context.get("paper_ids") or [])
    workspace_id = _coerce_int(context.get("workspace_id"), 0)
    if not paper_ids and workspace_id > 0:
        paper_ids = [int(paper.id) for paper in repo.list_papers_for_workspace(workspace_id)][:15]
    if not paper_ids:
        raise ValueError("Report intent requires workspace_id or paper_ids.")
    topic = query[:1000]
    report_result = await asyncio.to_thread(
        aggregate_and_generate_report,
        repo=repo,
        user_id=str(int(user_id)),
        paper_ids=paper_ids[:15],
        topic=topic,
    )
    if workspace_id > 0:
        mark_step_best_effort(
            repo=repo,
            user_id=int(user_id),
            workspace_id=int(workspace_id),
            step_id=ONBOARDING_STEP_REPORT,
        )
    sources = _collect_sources_from_papers(repo=repo, user_id=user_id, paper_ids=paper_ids)
    confidence = _clamp(0.68 + (0.03 * min(6, len(sources))))
    return {
        "type": INTENT_REPORT,
        "content": report_result if isinstance(report_result, dict) else {"summary": _safe_str(report_result)},
        "sources": sources,
        "confidence": round(confidence, 4),
    }


async def _route_insights(
    *,
    repo: ResearchRepository,
    user_id: int,
    query: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    workspace_id = _coerce_int(context.get("workspace_id"), 0)
    if workspace_id <= 0:
        paper_ids = _unique_ints(context.get("paper_ids") or [])
        if paper_ids:
            paper = repo.find_paper_for_user(paper_ids[0], int(user_id))
            workspace_id = _coerce_int(getattr(paper, "workspace_id", 0), 0) if paper else 0
    if workspace_id <= 0:
        raise ValueError("Insights intent requires workspace_id or paper_ids in context.")
    result = await get_or_generate_workspace_insights(
        repo=repo,
        workspace_id=workspace_id,
        user_id=int(user_id),
        refresh=False,
        run_inline=True,
        trigger="copilot_query",
    )
    insight = result.get("insight") if isinstance(result.get("insight"), dict) else {}
    payload = insight.get("payload") if isinstance(insight.get("payload"), dict) else {}
    sources = insight.get("sources") if isinstance(insight.get("sources"), list) else []
    confidence = _clamp(float(insight.get("confidence") or 0.58))
    return {
        "type": INTENT_INSIGHTS,
        "content": {
            "payload": payload,
            "disclaimer": _safe_str(insight.get("disclaimer")),
            "generated_at": insight.get("generated_at"),
            "expires_at": insight.get("expires_at"),
            "status": _safe_str(result.get("status")),
        },
        "sources": sources,
        "confidence": round(confidence, 4),
    }


async def _route_rag_query(
    *,
    repo: ResearchRepository,
    user_id: int,
    query: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    workspace_id = _coerce_int(context.get("workspace_id"), 0)
    if workspace_id <= 0:
        paper_ids = _unique_ints(context.get("paper_ids") or [])
        if paper_ids:
            paper = repo.find_paper_for_user(paper_ids[0], int(user_id))
            workspace_id = _coerce_int(getattr(paper, "workspace_id", 0), 0) if paper else 0
    if workspace_id <= 0:
        if not groq_client:
            return {
                "type": INTENT_RAG_QUERY,
                "content": {"answer": "Please provide workspace context or paper_ids so I can ground the response."},
                "sources": [],
                "confidence": 0.22,
            }
        ai_result = run_ai_query(
            groq_client=groq_client,
            db=getattr(repo, "db", None),
            user_id=str(int(user_id)),
            query=_safe_str(query)[:8000],
            system_prompt=(
                "You are Soyog AI Copilot. Respond concisely and ask for workspace or paper context "
                "when evidence is missing."
            ),
            route="copilot_general",
            model_kwargs=model_config(task="chat", max_tokens=1000, temperature=0.2),
            cacheable=True,
        )
        return {
            "type": INTENT_RAG_QUERY,
            "content": {"answer": _safe_str(ai_result.get("response")) or "I need more context to answer reliably."},
            "sources": [],
            "confidence": 0.3,
        }

    runtime = get_rag_runtime(db=getattr(repo, "db", None))
    results = await runtime.retrieval_service.retrieve(
        query=query,
        workspace_id=workspace_id,
        top_k=6,
        source_types=["paper", "summary", "checker", "report"],
        min_similarity=0.3,
    )
    truncated = runtime.retrieval_service.truncate_results_for_context(results, max_context_tokens=1800)
    context_rows = [
        {
            "vector_id": row.vector_id,
            "source_id": row.source_id,
            "source_type": row.source_type,
            "text": row.text,
            "similarity_score": row.similarity_score,
            "metadata": row.metadata,
        }
        for row in truncated
    ]
    rag_output = await runtime.rag_query_handler.handle(
        RAGQueryInput(
            query=query,
            retrieved_context=context_rows,
            strict_grounding=True,
            max_tokens=2000,
        ),
        db=getattr(repo, "db", None),
        user_id=str(int(user_id)),
    )
    sources = [
        {
            "source_id": source.source_id,
            "source_type": source.source_type,
            "title": source.title,
            "relevance_score": source.relevance_score,
        }
        for source in rag_output.sources_used
    ]
    return {
        "type": INTENT_RAG_QUERY,
        "content": {"answer": rag_output.answer},
        "sources": sources,
        "confidence": round(_clamp(float(rag_output.confidence)), 4),
    }


def _router_for_intent(intent: str):
    if intent == INTENT_EXPLAIN:
        return _route_explain
    if intent == INTENT_COMPARE:
        return _route_compare
    if intent == INTENT_REPORT:
        return _route_report
    if intent == INTENT_INSIGHTS:
        return _route_insights
    return _route_rag_query


async def run_unified_copilot(
    *,
    repo: ResearchRepository,
    user_id: int,
    query: str,
    context: Optional[Dict[str, Any]] = None,
    refresh: bool = False,
) -> Dict[str, Any]:
    trimmed_query = _safe_str(query)
    if len(trimmed_query) < 2:
        raise ValueError("query must be at least 2 characters.")

    resolved_context = _resolve_context(
        repo=repo,
        user_id=int(user_id),
        context=context,
    )

    cache_key = _cache_key_for_request(
        user_id=int(user_id),
        query=trimmed_query,
        context=resolved_context,
    )
    if not refresh:
        memory_hit = get_memory_cache(cache_key)
        if memory_hit:
            parsed = _parse_cached_payload(memory_hit)
            if parsed:
                parsed["cached"] = True
                parsed["cache_layer"] = "memory"
                return parsed
        firestore_hit = get_cached_response(getattr(repo, "db", None), cache_key)
        if firestore_hit:
            parsed = _parse_cached_payload(firestore_hit)
            if parsed:
                parsed["cached"] = True
                parsed["cache_layer"] = "firestore"
                return parsed

    intent_meta = detect_copilot_intent(query=trimmed_query, context=resolved_context)
    detected_intent = _safe_str(intent_meta.get("intent")) or INTENT_RAG_QUERY
    fallback_used = bool(intent_meta.get("unclear"))

    try:
        routed = await _router_for_intent(detected_intent)(
            repo=repo,
            user_id=int(user_id),
            query=trimmed_query,
            context=resolved_context,
        )
    except Exception as exc:
        logger.warning(
            "copilot route failed intent=%s user_id=%s: %s",
            detected_intent,
            user_id,
            exc,
        )
        routed = await _route_rag_query(
            repo=repo,
            user_id=int(user_id),
            query=trimmed_query,
            context=resolved_context,
        )
        fallback_used = True

    response = {
        "type": _safe_str(routed.get("type")) or detected_intent,
        "intent": detected_intent,
        "content": routed.get("content"),
        "sources": routed.get("sources") if isinstance(routed.get("sources"), list) else [],
        "confidence": round(
            _clamp(
                (float(routed.get("confidence") or 0.0) * 0.8)
                + (float(intent_meta.get("intent_confidence") or 0.0) * 0.2)
            ),
            4,
        ),
        "fallback_used": bool(fallback_used),
        "cached": False,
        "cache_layer": None,
        "intent_scores": intent_meta.get("scores") if isinstance(intent_meta.get("scores"), dict) else {},
        "context": resolved_context,
    }

    try:
        set_cached_response(
            getattr(repo, "db", None),
            cache_key,
            json.dumps(response, ensure_ascii=True),
            route="ai_copilot",
            user_id=str(int(user_id)),
        )
    except Exception:
        logger.debug("copilot cache write skipped for user_id=%s", user_id)

    return response
