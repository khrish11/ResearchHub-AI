from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from repositories.vector_repository import VectorSearchMatch, VectorStore
from services.embedding_service import EmbeddingService, estimate_tokens


@dataclass
class RetrievalResult:
    vector_id: str
    source_id: str
    source_type: str
    chunk_index: int
    text: str
    similarity_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


class RetrievalService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        *,
        similarity_threshold: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
    ) -> None:
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.similarity_threshold = float(
            similarity_threshold
            if similarity_threshold is not None
            else (os.getenv("RAG_SIMILARITY_THRESHOLD", "0.45") or 0.45)
        )
        self.max_context_tokens = int(
            max_context_tokens
            if max_context_tokens is not None
            else (os.getenv("RAG_MAX_CONTEXT_TOKENS", "2200") or 2200)
        )

    @staticmethod
    def _from_match(match: VectorSearchMatch) -> RetrievalResult:
        return RetrievalResult(
            vector_id=match.vector_id,
            source_id=match.source_id,
            source_type=match.source_type,
            chunk_index=match.chunk_index,
            text=match.text,
            similarity_score=float(match.similarity_score),
            metadata=dict(match.metadata or {}),
            created_at=match.created_at,
        )

    async def retrieve(
        self,
        *,
        query: str,
        workspace_id: int,
        top_k: int = 5,
        source_types: Optional[Sequence[str]] = None,
        min_similarity: Optional[float] = None,
    ) -> List[RetrievalResult]:
        normalized = str(query or "").strip()
        if not normalized:
            return []
        threshold = (
            float(min_similarity)
            if min_similarity is not None
            else float(self.similarity_threshold)
        )
        query_embedding = await self.embedding_service.embed(normalized)
        matches = await self.vector_store.search(
            query_embedding=query_embedding,
            workspace_id=int(workspace_id),
            top_k=max(1, int(top_k)),
            source_types=source_types,
            min_similarity=threshold,
        )
        return [self._from_match(match) for match in matches]

    def _truncate_by_tokens(
        self,
        results: Sequence[RetrievalResult],
        *,
        max_context_tokens: Optional[int] = None,
    ) -> List[RetrievalResult]:
        budget = max(200, int(max_context_tokens or self.max_context_tokens))
        used = 0
        kept: List[RetrievalResult] = []
        for result in results:
            token_cost = estimate_tokens(result.text) + 32
            if kept and (used + token_cost) > budget:
                break
            kept.append(result)
            used += token_cost
        return kept

    def truncate_results_for_context(
        self,
        results: Sequence[RetrievalResult],
        *,
        max_context_tokens: Optional[int] = None,
    ) -> List[RetrievalResult]:
        return self._truncate_by_tokens(results, max_context_tokens=max_context_tokens)

    def format_for_prompt(
        self,
        results: Sequence[RetrievalResult],
        *,
        max_context_tokens: Optional[int] = None,
    ) -> str:
        trimmed = self._truncate_by_tokens(results, max_context_tokens=max_context_tokens)
        if not trimmed:
            return "No relevant workspace context retrieved."
        lines: List[str] = ["## Retrieved Context"]
        for idx, item in enumerate(trimmed, start=1):
            title = str((item.metadata or {}).get("title") or "").strip() or "Untitled"
            lines.append(f"\n### Source {idx}")
            lines.append(f"- source_id: {item.source_id}")
            lines.append(f"- source_type: {item.source_type}")
            lines.append(f"- title: {title}")
            lines.append(f"- similarity: {item.similarity_score:.3f}")
            lines.append(item.text.strip())
        return "\n".join(lines).strip()

    async def retrieve_and_format(
        self,
        *,
        query: str,
        workspace_id: int,
        top_k: int = 5,
        source_types: Optional[Sequence[str]] = None,
        min_similarity: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
    ) -> str:
        results = await self.retrieve(
            query=query,
            workspace_id=workspace_id,
            top_k=top_k,
            source_types=source_types,
            min_similarity=min_similarity,
        )
        return self.format_for_prompt(results, max_context_tokens=max_context_tokens)

    def retrieve_and_format_sync(
        self,
        *,
        query: str,
        workspace_id: int,
        top_k: int = 5,
        source_types: Optional[Sequence[str]] = None,
        min_similarity: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
    ) -> str:
        async def _run() -> str:
            return await self.retrieve_and_format(
                query=query,
                workspace_id=workspace_id,
                top_k=top_k,
                source_types=source_types,
                min_similarity=min_similarity,
                max_context_tokens=max_context_tokens,
            )

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_run())
        raise RuntimeError("retrieve_and_format_sync cannot run inside an active event loop.")
