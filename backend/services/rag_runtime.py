from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict

from repositories.vector_repository import VectorStore, build_vector_store
from services.embedding_service import EmbeddingService
from services.rag_query_handler import RAGQueryHandler
from services.retrieval_service import RetrievalService
from utils.groq_client import client as groq_client


@dataclass(frozen=True)
class RAGRuntime:
    embedding_service: EmbeddingService
    vector_store: VectorStore
    retrieval_service: RetrievalService
    rag_query_handler: RAGQueryHandler


_RUNTIME_CACHE: Dict[str, RAGRuntime] = {}
_RUNTIME_LOCK = Lock()


def _runtime_key(db: Any) -> str:
    if db is None:
        return "memory"
    return f"db:{id(db)}"


def get_rag_runtime(*, db: Any = None) -> RAGRuntime:
    key = _runtime_key(db)
    with _RUNTIME_LOCK:
        existing = _RUNTIME_CACHE.get(key)
        if existing is not None:
            return existing
        embedding = EmbeddingService()
        vector_store = build_vector_store(db=db)
        retrieval = RetrievalService(embedding, vector_store)
        handler = RAGQueryHandler(groq_client_ref=groq_client)
        runtime = RAGRuntime(
            embedding_service=embedding,
            vector_store=vector_store,
            retrieval_service=retrieval,
            rag_query_handler=handler,
        )
        _RUNTIME_CACHE[key] = runtime
        return runtime


def reset_rag_runtime_cache() -> None:
    with _RUNTIME_LOCK:
        _RUNTIME_CACHE.clear()
