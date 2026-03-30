from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from services.ai_service import run_ai_query
from utils.groq_client import model_config


logger = logging.getLogger(__name__)

_SOURCE_TAG_RE = re.compile(
    r"(?:\[?\s*source\s+(\d+)\s*\]?|\[?\s*s(\d+)\s*\]?)",
    re.IGNORECASE,
)


@dataclass
class SourceAttribution:
    source_id: str
    source_type: str
    title: Optional[str] = None
    mention_count: int = 0
    relevance_score: float = 0.0


@dataclass
class RAGQueryInput:
    query: str
    retrieved_context: List[Dict[str, Any]]
    max_tokens: int = 1400
    strict_grounding: bool = True


@dataclass
class RAGQueryOutput:
    answer: str
    sources_used: List[SourceAttribution] = field(default_factory=list)
    confidence: float = 0.0
    grounding_score: float = 0.0
    invalid_source_refs: List[int] = field(default_factory=list)


class RAGQueryHandler:
    def __init__(self, *, groq_client_ref: Any = None) -> None:
        self.groq_client = groq_client_ref

    def _build_system_prompt(self, *, strict_grounding: bool) -> str:
        grounding_line = (
            "Only answer from provided sources; if context is insufficient, explicitly say so."
            if strict_grounding
            else "Prioritize provided sources and clearly mark uncertainty."
        )
        return (
            "You are Soyog AI's workspace research assistant.\n"
            f"{grounding_line}\n"
            "Cite evidence inline using [Source N] markers.\n"
            "Never invent a source. Never cite a source number not present in context.\n"
            "When uncertain, say: 'Insufficient evidence in workspace context.'"
        )

    def _format_context(self, rows: Sequence[Dict[str, Any]]) -> str:
        if not rows:
            return "No context provided."
        blocks: List[str] = []
        for idx, row in enumerate(rows, start=1):
            metadata = row.get("metadata") or {}
            title = str(metadata.get("title") or "Untitled").strip()
            source_type = str(row.get("source_type") or "unknown").strip()
            source_id = str(row.get("source_id") or f"source_{idx}").strip()
            similarity = float(row.get("similarity_score") or 0.0)
            text = str(row.get("text") or "").strip()
            blocks.append(
                "\n".join(
                    [
                        f"### Source {idx}",
                        f"- id: {source_id}",
                        f"- type: {source_type}",
                        f"- title: {title}",
                        f"- similarity: {similarity:.3f}",
                        text,
                    ]
                )
            )
        return "\n\n".join(blocks)

    def _build_user_prompt(self, payload: RAGQueryInput) -> str:
        return (
            "## Workspace Context\n"
            f"{self._format_context(payload.retrieved_context)}\n\n"
            f"## User Question\n{payload.query}\n\n"
            "## Response Rules\n"
            "- Start with a direct answer.\n"
            "- Then provide supporting evidence with [Source N] citations.\n"
            "- If evidence is incomplete, add a short limitations note."
        )

    async def _query_llm(
        self,
        *,
        db: Any,
        user_id: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
    ) -> str:
        if not self.groq_client:
            raise RuntimeError("RAG query unavailable: Groq client is not configured.")
        result = await asyncio.to_thread(
            run_ai_query,
            groq_client=self.groq_client,
            db=db,
            user_id=str(user_id or "anonymous"),
            query=user_prompt,
            system_prompt=system_prompt,
            route="rag_query",
            model_kwargs=model_config(
                task="pipeline",
                longform=False,
                max_tokens=min(max(250, int(max_tokens)), 2200),
                temperature=0.08,
            ),
            cacheable=False,
            timeout_seconds=60,
        )
        response = str(result.get("response") or "").strip()
        if not response:
            raise RuntimeError(str(result.get("error") or "RAG model returned an empty response."))
        return response

    def _extract_source_indexes(self, answer: str) -> List[int]:
        indexes: List[int] = []
        for match in _SOURCE_TAG_RE.findall(answer or ""):
            raw = match[0] or match[1]
            if not raw:
                continue
            try:
                idx = int(raw)
            except ValueError:
                continue
            if idx > 0:
                indexes.append(idx)
        return indexes

    def _extract_sources(
        self,
        *,
        answer: str,
        retrieved_context: Sequence[Dict[str, Any]],
    ) -> tuple[List[SourceAttribution], List[int]]:
        indexes = self._extract_source_indexes(answer)
        if not indexes:
            return [], []
        used: Dict[str, SourceAttribution] = {}
        invalid_refs: List[int] = []
        for idx in indexes:
            if idx < 1 or idx > len(retrieved_context):
                invalid_refs.append(idx)
                continue
            row = retrieved_context[idx - 1]
            source_id = str(row.get("source_id") or f"source_{idx}")
            item = used.get(source_id)
            if item is None:
                metadata = row.get("metadata") or {}
                item = SourceAttribution(
                    source_id=source_id,
                    source_type=str(row.get("source_type") or "unknown"),
                    title=str(metadata.get("title") or "").strip() or None,
                    mention_count=0,
                    relevance_score=float(row.get("similarity_score") or 0.0),
                )
                used[source_id] = item
            item.mention_count += 1
        return list(used.values()), sorted(set(invalid_refs))

    def _calculate_grounding_score(
        self,
        *,
        answer: str,
        source_indexes: Sequence[int],
        invalid_source_refs: Sequence[int],
    ) -> float:
        words = max(1, len(str(answer or "").split()))
        expected_mentions = max(1, words // 90)
        mention_factor = min(1.0, len(source_indexes) / expected_mentions)
        penalty = min(0.7, 0.25 * len(invalid_source_refs))
        return max(0.0, mention_factor - penalty)

    def _calculate_confidence(
        self,
        *,
        sources: Sequence[SourceAttribution],
        context_count: int,
        grounding_score: float,
    ) -> float:
        if not sources:
            return max(0.0, min(0.35, grounding_score))
        coverage = min(1.0, len(sources) / max(1, context_count))
        avg_relevance = sum(max(0.0, src.relevance_score) for src in sources) / max(1, len(sources))
        confidence = (0.45 * coverage) + (0.35 * avg_relevance) + (0.20 * grounding_score)
        return max(0.0, min(1.0, confidence))

    async def handle(
        self,
        payload: RAGQueryInput,
        *,
        db: Any,
        user_id: str,
    ) -> RAGQueryOutput:
        question = str(payload.query or "").strip()
        if not question:
            raise ValueError("Query cannot be empty.")
        if not payload.retrieved_context:
            return RAGQueryOutput(
                answer="Insufficient evidence in workspace context.",
                sources_used=[],
                confidence=0.0,
                grounding_score=0.0,
                invalid_source_refs=[],
            )

        system_prompt = self._build_system_prompt(strict_grounding=payload.strict_grounding)
        user_prompt = self._build_user_prompt(payload)
        answer = await self._query_llm(
            db=db,
            user_id=user_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=payload.max_tokens,
        )

        sources_used, invalid_refs = self._extract_sources(
            answer=answer,
            retrieved_context=payload.retrieved_context,
        )
        source_indexes = self._extract_source_indexes(answer)
        grounding_score = self._calculate_grounding_score(
            answer=answer,
            source_indexes=source_indexes,
            invalid_source_refs=invalid_refs,
        )
        confidence = self._calculate_confidence(
            sources=sources_used,
            context_count=len(payload.retrieved_context),
            grounding_score=grounding_score,
        )
        if invalid_refs:
            logger.warning(
                "RAG response referenced unavailable sources: %s",
                invalid_refs,
            )
        return RAGQueryOutput(
            answer=answer,
            sources_used=sources_used,
            confidence=confidence,
            grounding_score=grounding_score,
            invalid_source_refs=invalid_refs,
        )
