from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict

from repositories.vector_repository import VectorStore, build_vector_store, InMemoryVectorStore, FirestoreVectorStore
from services.embedding_service import EmbeddingService
from services.rag_query_handler import RAGQueryHandler
from services.retrieval_service import RetrievalService
from utils.groq_client import client as groq_client

logger = logging.getLogger(__name__)


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
        
        # Log the storage backend configuration
        store_type = type(vector_store).__name__
        firestore_info = {}
        if isinstance(vector_store, FirestoreVectorStore):
            firestore_info = {
                "collection": getattr(vector_store, "collection_name", "unknown"),
                "db_provided": db is not None,
            }
        elif isinstance(vector_store, InMemoryVectorStore):
            firestore_info = {
                "warning": "InMemoryVectorStore - vectors will not persist across restarts",
                "db_provided": db is not None,
            }
        
        logger.info("RAG_STORAGE_BACKEND", extra={
            "repository": store_type,
            "vector_store": store_type,
            "database": "Firestore" if db is not None else "None",
            "firestore_enabled": db is not None,
            "emulator_host": "localhost:8081" if db is not None else "N/A",
            "collection": firestore_info.get("collection", "N/A"),
            "in_memory_warning": firestore_info.get("warning", None),
        })
        
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
