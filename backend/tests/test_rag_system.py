from __future__ import annotations

import pytest

from repositories.vector_repository import (
    InMemoryVectorStore,
    VectorDocument,
    cosine_similarity,
)
from services.rag_query_handler import RAGQueryHandler, RAGQueryInput
from services.retrieval_service import RetrievalService


class _FakeEmbeddingService:
    async def embed(self, text: str):  # noqa: ANN201
        if "attention" in text.lower():
            return [1.0, 0.0, 0.0]
        return [0.0, 1.0, 0.0]

    async def batch_embed(self, texts):  # noqa: ANN201, ANN001
        return [await self.embed(text) for text in texts]


def test_cosine_similarity_basic() -> None:
    assert cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)
    assert cosine_similarity([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0)
    assert cosine_similarity([0, 0, 0], [0, 0, 0]) == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_in_memory_vector_store_workspace_isolation() -> None:
    store = InMemoryVectorStore()
    await store.upsert(
        VectorDocument(
            id="v1",
            workspace_id=1,
            source_id="p1",
            source_type="paper",
            text="attention mechanism improves translation",
            embedding=[1.0, 0.0, 0.0],
        )
    )
    await store.upsert(
        VectorDocument(
            id="v2",
            workspace_id=2,
            source_id="p2",
            source_type="paper",
            text="different workspace vector",
            embedding=[1.0, 0.0, 0.0],
        )
    )

    hits = await store.search(
        query_embedding=[1.0, 0.0, 0.0],
        workspace_id=1,
        top_k=5,
        source_types=None,
    )
    assert len(hits) == 1
    assert hits[0].source_id == "p1"


@pytest.mark.asyncio
async def test_retrieval_service_returns_ranked_results() -> None:
    store = InMemoryVectorStore()
    await store.upsert(
        VectorDocument(
            id="v1",
            workspace_id=1,
            source_id="p1",
            source_type="paper",
            text="attention mechanism for machine translation",
            embedding=[1.0, 0.0, 0.0],
            metadata={"title": "Attention Is All You Need"},
        )
    )
    await store.upsert(
        VectorDocument(
            id="v2",
            workspace_id=1,
            source_id="p2",
            source_type="paper",
            text="graph neural network for molecules",
            embedding=[0.0, 1.0, 0.0],
            metadata={"title": "Molecular GNN"},
        )
    )

    retrieval = RetrievalService(
        embedding_service=_FakeEmbeddingService(),  # type: ignore[arg-type]
        vector_store=store,
        similarity_threshold=0.1,
        max_context_tokens=300,
    )

    rows = await retrieval.retrieve(
        query="attention",
        workspace_id=1,
        top_k=3,
        source_types=["paper"],
    )
    assert rows
    assert rows[0].source_id == "p1"

    formatted = retrieval.format_for_prompt(rows, max_context_tokens=180)
    assert "Retrieved Context" in formatted
    assert "Source 1" in formatted


@pytest.mark.asyncio
async def test_rag_handler_no_context() -> None:
    handler = RAGQueryHandler(groq_client_ref=None)
    result = await handler.handle(
        RAGQueryInput(query="what are trends", retrieved_context=[]),
        db=None,
        user_id="u1",
    )
    assert "Insufficient evidence" in result.answer
    assert result.confidence == pytest.approx(0.0)
    assert result.grounding_score == pytest.approx(0.0)


def test_rag_source_extraction_and_invalid_refs() -> None:
    handler = RAGQueryHandler(groq_client_ref=None)
    rows = [
        {"source_id": "p1", "source_type": "paper", "similarity_score": 0.91},
        {"source_id": "p2", "source_type": "paper", "similarity_score": 0.74},
    ]
    sources, invalid = handler._extract_sources(  # noqa: SLF001
        answer="According to [Source 1] and [Source 2], results are mixed. [Source 9]",
        retrieved_context=rows,
    )
    assert len(sources) == 2
    assert invalid == [9]
