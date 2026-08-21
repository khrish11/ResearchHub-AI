from __future__ import annotations

import asyncio
import hashlib
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence

from google.cloud.firestore_v1.base_query import FieldFilter


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _safe_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return _utcnow()


def _normalize_source_type(value: str) -> str:
    text = str(value or "").strip().lower()
    return text or "unknown"


def cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    size = min(len(vec_a), len(vec_b))
    if size <= 0:
        return 0.0
    dot = 0.0
    mag_a = 0.0
    mag_b = 0.0
    for idx in range(size):
        left = float(vec_a[idx])
        right = float(vec_b[idx])
        dot += left * right
        mag_a += left * left
        mag_b += right * right
    denom = math.sqrt(mag_a) * math.sqrt(mag_b)
    if denom <= 0.0:
        return 0.0
    return dot / denom


def compute_text_hash(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


@dataclass
class VectorDocument:
    id: str
    workspace_id: int
    source_id: str
    source_type: str
    text: str
    embedding: List[float]
    chunk_index: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    text_hash: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        self.source_type = _normalize_source_type(self.source_type)
        self.text_hash = self.text_hash or compute_text_hash(self.text)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workspace_id": int(self.workspace_id),
            "source_id": str(self.source_id),
            "source_type": self.source_type,
            "text": str(self.text or ""),
            "embedding": [float(v) for v in self.embedding],
            "chunk_index": int(self.chunk_index),
            "metadata": dict(self.metadata or {}),
            "text_hash": self.text_hash,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "VectorDocument":
        return cls(
            id=str(payload.get("id") or ""),
            workspace_id=int(payload.get("workspace_id") or 0),
            source_id=str(payload.get("source_id") or ""),
            source_type=str(payload.get("source_type") or ""),
            text=str(payload.get("text") or ""),
            embedding=[float(v) for v in (payload.get("embedding") or [])],
            chunk_index=int(payload.get("chunk_index") or 0),
            metadata=dict(payload.get("metadata") or {}),
            text_hash=str(payload.get("text_hash") or ""),
            created_at=_safe_datetime(payload.get("created_at")),
            updated_at=_safe_datetime(payload.get("updated_at")),
        )


@dataclass
class VectorSearchMatch:
    vector_id: str
    workspace_id: int
    source_id: str
    source_type: str
    text: str
    embedding: List[float]
    similarity_score: float
    chunk_index: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)


class VectorStore(Protocol):
    async def upsert(self, document: VectorDocument) -> str: ...

    async def upsert_many(self, documents: Sequence[VectorDocument]) -> int: ...

    async def get(self, vector_id: str) -> Optional[VectorDocument]: ...

    async def delete(self, vector_id: str) -> None: ...

    async def delete_by_source(
        self,
        *,
        workspace_id: int,
        source_id: str,
        source_type: Optional[str] = None,
    ) -> int: ...

    async def search(
        self,
        *,
        query_embedding: Sequence[float],
        workspace_id: int,
        top_k: int,
        source_types: Optional[Sequence[str]] = None,
        min_similarity: float = 0.0,
    ) -> List[VectorSearchMatch]: ...

    async def count_by_workspace(self, workspace_id: int) -> int: ...


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._docs: Dict[str, VectorDocument] = {}
        self._lock = Lock()

    async def upsert(self, document: VectorDocument) -> str:
        with self._lock:
            self._docs[document.id] = document
        return document.id

    async def upsert_many(self, documents: Sequence[VectorDocument]) -> int:
        with self._lock:
            for item in documents:
                self._docs[item.id] = item
        return len(documents)

    async def get(self, vector_id: str) -> Optional[VectorDocument]:
        with self._lock:
            doc = self._docs.get(str(vector_id))
        return doc

    async def delete(self, vector_id: str) -> None:
        with self._lock:
            self._docs.pop(str(vector_id), None)

    async def delete_by_source(
        self,
        *,
        workspace_id: int,
        source_id: str,
        source_type: Optional[str] = None,
    ) -> int:
        target_type = _normalize_source_type(source_type) if source_type else None
        removed = 0
        with self._lock:
            for vector_id, doc in list(self._docs.items()):
                if int(doc.workspace_id) != int(workspace_id):
                    continue
                if str(doc.source_id) != str(source_id):
                    continue
                if target_type and doc.source_type != target_type:
                    continue
                self._docs.pop(vector_id, None)
                removed += 1
        return removed

    async def search(
        self,
        *,
        query_embedding: Sequence[float],
        workspace_id: int,
        top_k: int,
        source_types: Optional[Sequence[str]] = None,
        min_similarity: float = 0.0,
    ) -> List[VectorSearchMatch]:
        target_types = {
            _normalize_source_type(item) for item in (source_types or []) if str(item).strip()
        }
        matches: List[VectorSearchMatch] = []
        with self._lock:
            docs = list(self._docs.values())
        for doc in docs:
            if int(doc.workspace_id) != int(workspace_id):
                continue
            if target_types and doc.source_type not in target_types:
                continue
            score = cosine_similarity(query_embedding, doc.embedding)
            if score < float(min_similarity):
                continue
            matches.append(
                VectorSearchMatch(
                    vector_id=doc.id,
                    workspace_id=doc.workspace_id,
                    source_id=doc.source_id,
                    source_type=doc.source_type,
                    text=doc.text,
                    embedding=list(doc.embedding),
                    similarity_score=score,
                    chunk_index=doc.chunk_index,
                    metadata=dict(doc.metadata or {}),
                    created_at=doc.created_at,
                )
            )
        matches.sort(
            key=lambda item: (item.similarity_score, item.created_at.timestamp()),
            reverse=True,
        )
        return matches[: max(1, int(top_k))]

    async def count_by_workspace(self, workspace_id: int) -> int:
        with self._lock:
            return sum(
                1 for item in self._docs.values() if int(item.workspace_id) == int(workspace_id)
            )


class FirestoreVectorStore:
    def __init__(self, db: Any, *, collection_name: Optional[str] = None) -> None:
        if db is None:
            raise ValueError("FirestoreVectorStore requires a Firestore client.")
        self.db = db
        self.collection_name = str(
            collection_name
            or os.getenv("RAG_VECTOR_COLLECTION")
            or "workspace_vectors"
        ).strip()
        self.collection = self.db.collection(self.collection_name)

    def _query_docs(
        self, *, workspace_id: int, source_types: Optional[Sequence[str]]
    ) -> List[VectorDocument]:
        query = self.collection.where(
            filter=FieldFilter("workspace_id", "==", int(workspace_id))
        )
        normalized_types = [
            _normalize_source_type(item) for item in (source_types or []) if str(item).strip()
        ]
        try:
            if len(normalized_types) == 1:
                query = query.where(
                    filter=FieldFilter("source_type", "==", normalized_types[0])
                )
            elif 1 < len(normalized_types) <= 10:
                query = query.where(
                    filter=FieldFilter("source_type", "in", normalized_types)
                )
        except Exception:
            # Some emulator/runtime versions do not support where(..., "in", ...).
            pass
        docs: List[VectorDocument] = []
        for snapshot in query.stream():
            payload = snapshot.to_dict() or {}
            payload["id"] = payload.get("id") or snapshot.id
            doc = VectorDocument.from_dict(payload)
            if normalized_types and doc.source_type not in set(normalized_types):
                continue
            docs.append(doc)
        return docs

    async def upsert(self, document: VectorDocument) -> str:
        return await asyncio.to_thread(self._upsert_sync, document)

    def _upsert_sync(self, document: VectorDocument) -> str:
        payload = document.to_dict()
        payload["updated_at"] = _utcnow()
        self.collection.document(document.id).set(payload, merge=True)
        return document.id

    async def upsert_many(self, documents: Sequence[VectorDocument]) -> int:
        return await asyncio.to_thread(self._upsert_many_sync, documents)

    def _upsert_many_sync(self, documents: Sequence[VectorDocument]) -> int:
        batch = self.db.batch()
        count = 0
        now = _utcnow()
        for doc in documents:
            payload = doc.to_dict()
            payload["updated_at"] = now
            batch.set(self.collection.document(doc.id), payload, merge=True)
            count += 1
        if count > 0:
            batch.commit()
        return count

    async def get(self, vector_id: str) -> Optional[VectorDocument]:
        return await asyncio.to_thread(self._get_sync, vector_id)

    def _get_sync(self, vector_id: str) -> Optional[VectorDocument]:
        snapshot = self.collection.document(str(vector_id)).get()
        if not snapshot.exists:
            return None
        payload = snapshot.to_dict() or {}
        payload["id"] = payload.get("id") or snapshot.id
        return VectorDocument.from_dict(payload)

    async def delete(self, vector_id: str) -> None:
        await asyncio.to_thread(self.collection.document(str(vector_id)).delete)

    async def delete_by_source(
        self,
        *,
        workspace_id: int,
        source_id: str,
        source_type: Optional[str] = None,
    ) -> int:
        return await asyncio.to_thread(
            self._delete_by_source_sync,
            workspace_id,
            source_id,
            source_type,
        )

    def _delete_by_source_sync(
        self,
        workspace_id: int,
        source_id: str,
        source_type: Optional[str],
    ) -> int:
        query = (
            self.collection.where(
                filter=FieldFilter("workspace_id", "==", int(workspace_id))
            ).where(
                filter=FieldFilter("source_id", "==", str(source_id))
            )
        )
        if source_type:
            query = query.where(
                filter=FieldFilter("source_type", "==", _normalize_source_type(source_type))
            )
        removed = 0
        batch = self.db.batch()
        for snapshot in query.stream():
            batch.delete(snapshot.reference)
            removed += 1
        if removed:
            batch.commit()
        return removed

    async def search(
        self,
        *,
        query_embedding: Sequence[float],
        workspace_id: int,
        top_k: int,
        source_types: Optional[Sequence[str]] = None,
        min_similarity: float = 0.0,
    ) -> List[VectorSearchMatch]:
        return await asyncio.to_thread(
            self._search_sync,
            list(query_embedding),
            int(workspace_id),
            int(top_k),
            source_types,
            float(min_similarity),
        )

    def _search_sync(
        self,
        query_embedding: List[float],
        workspace_id: int,
        top_k: int,
        source_types: Optional[Sequence[str]],
        min_similarity: float,
    ) -> List[VectorSearchMatch]:
        docs = self._query_docs(workspace_id=workspace_id, source_types=source_types)
        matches: List[VectorSearchMatch] = []
        for doc in docs:
            score = cosine_similarity(query_embedding, doc.embedding)
            if score < min_similarity:
                continue
            matches.append(
                VectorSearchMatch(
                    vector_id=doc.id,
                    workspace_id=doc.workspace_id,
                    source_id=doc.source_id,
                    source_type=doc.source_type,
                    text=doc.text,
                    embedding=list(doc.embedding),
                    similarity_score=score,
                    chunk_index=doc.chunk_index,
                    metadata=dict(doc.metadata or {}),
                    created_at=doc.created_at,
                )
            )
        matches.sort(
            key=lambda item: (item.similarity_score, item.created_at.timestamp()),
            reverse=True,
        )
        return matches[: max(1, top_k)]

    async def count_by_workspace(self, workspace_id: int) -> int:
        return await asyncio.to_thread(self._count_by_workspace_sync, workspace_id)

    def _count_by_workspace_sync(self, workspace_id: int) -> int:
        query = self.collection.where(
            filter=FieldFilter("workspace_id", "==", int(workspace_id))
        )
        return sum(1 for _ in query.stream())


_IN_MEMORY_STORE_SINGLETON: Optional[InMemoryVectorStore] = None
_STORE_LOCK = Lock()


def build_vector_store(*, db: Any = None) -> VectorStore:
    """
    Build a vector store instance.
    
    Production:
    - Requires a Firestore db instance (passed via db parameter)
    - Falls back to FirestoreVectorStore for persistent vector storage
    
    Development:
    - Falls back to InMemoryVectorStore if db is None
    - Useful for local development and testing
    """
    app_env = str(os.getenv("APP_ENV", "production") or "production").strip().lower()
    
    if db is not None:
        return FirestoreVectorStore(db)
    
    if app_env == "production":
        raise RuntimeError(
            "Production environment requires Firestore db for vector store. "
            "Pass a Firestore client instance to build_vector_store()."
        )
    
    logging.getLogger(__name__).warning(
        "No Firestore db provided; using InMemoryVectorStore (vectors will not persist across restarts)"
    )
    global _IN_MEMORY_STORE_SINGLETON
    with _STORE_LOCK:
        if _IN_MEMORY_STORE_SINGLETON is None:
            _IN_MEMORY_STORE_SINGLETON = InMemoryVectorStore()
        return _IN_MEMORY_STORE_SINGLETON
