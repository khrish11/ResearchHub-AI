from __future__ import annotations

import asyncio
import hashlib
import importlib
import logging
import math
import os
import re
from threading import Lock
from typing import Dict, List, Sequence

SentenceTransformer = None  # type: ignore[assignment]
_SENTENCE_TRANSFORMER_IMPORT_ERROR: Exception | None = None


logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)
_DEFAULT_EMBEDDING_DIM = max(32, int(os.getenv("RAG_EMBEDDING_DIM", "384") or 384))
_DEFAULT_CHUNK_SIZE = max(300, int(os.getenv("RAG_CHUNK_SIZE_CHARS", "1200") or 1200))
_DEFAULT_CHUNK_OVERLAP = max(40, int(os.getenv("RAG_CHUNK_OVERLAP_CHARS", "180") or 180))


def normalize_vector(values: Sequence[float], *, dim: int) -> List[float]:
    vector = [float(v) for v in values[:dim]]
    if len(vector) < dim:
        vector.extend([0.0] * (dim - len(vector)))
    magnitude = math.sqrt(sum(item * item for item in vector))
    if magnitude <= 0.0:
        return [0.0] * dim
    return [item / magnitude for item in vector]


def estimate_tokens(text: str) -> int:
    # A practical approximation for context budgeting in prompts.
    return max(1, int(len(str(text or "")) / 4))


def chunk_text(
    text: str,
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    overlap: int = _DEFAULT_CHUNK_OVERLAP,
) -> List[str]:
    normalized = str(text or "").strip()
    if not normalized:
        return []
    safe_overlap = min(max(0, overlap), max(0, chunk_size - 1))
    step = max(1, chunk_size - safe_overlap)
    chunks: List[str] = []
    for start in range(0, len(normalized), step):
        chunk = normalized[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


class EmbeddingService:
    """
    Embedding service with sentence-transformers primary path and a deterministic
    hashing fallback for environments where model load/inference is unavailable.
    """

    _shared_model = None
    _shared_model_name: str | None = None
    _model_lock = Lock()

    @staticmethod
    def _resolve_sentence_transformer_class():
        global SentenceTransformer, _SENTENCE_TRANSFORMER_IMPORT_ERROR
        if SentenceTransformer is not None:
            return SentenceTransformer
        if _SENTENCE_TRANSFORMER_IMPORT_ERROR is not None:
            return None
        try:
            module = importlib.import_module("sentence_transformers")
            SentenceTransformer = getattr(module, "SentenceTransformer", None)
            return SentenceTransformer
        except Exception as exc:  # pragma: no cover - optional runtime dependency
            _SENTENCE_TRANSFORMER_IMPORT_ERROR = exc
            logger.warning(
                "sentence-transformers import unavailable; using hashing embeddings."
            )
            return None

    def __init__(
        self,
        *,
        model_name: str | None = None,
        embedding_dim: int = _DEFAULT_EMBEDDING_DIM,
        max_text_chars: int = 12000,
    ) -> None:
        self.provider = str(
            os.getenv("RAG_EMBEDDING_PROVIDER") or "auto"
        ).strip().lower()
        self.allow_download = str(
            os.getenv("RAG_EMBEDDING_ALLOW_DOWNLOAD") or "0"
        ).strip().lower() in {"1", "true", "yes"}
        self.model_name = str(
            model_name
            or os.getenv("RAG_EMBEDDING_MODEL")
            or os.getenv("EMBEDDING_MODEL")
            or "all-MiniLM-L6-v2"
        ).strip()
        self.embedding_dim = max(32, int(embedding_dim))
        self.max_text_chars = max(1000, int(max_text_chars))
        self._memory_cache: Dict[str, List[float]] = {}
        self._cache_lock = Lock()

    def _normalized_text(self, text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return ""
        if len(value) > self.max_text_chars:
            return value[: self.max_text_chars]
        return value

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"{self.model_name}:{self.embedding_dim}:{digest}"

    def _get_model(self):
        if self.provider in {"hash", "hashing", "none"}:
            return None
        sentence_transformer_class = self._resolve_sentence_transformer_class()
        if sentence_transformer_class is None:
            return None
        with self._model_lock:
            if (
                EmbeddingService._shared_model is None
                or EmbeddingService._shared_model_name != self.model_name
            ):
                try:
                    model_kwargs: Dict[str, object] = {}
                    if not self.allow_download:
                        model_kwargs["local_files_only"] = True
                    EmbeddingService._shared_model = sentence_transformer_class(
                        self.model_name, **model_kwargs
                    )
                    EmbeddingService._shared_model_name = self.model_name
                except Exception as exc:  # pragma: no cover - network/model availability
                    logger.warning(
                        "Embedding model load failed for '%s' (provider=%s): %s. Falling back to hashing embeddings.",
                        self.model_name,
                        self.provider,
                        exc,
                    )
                    EmbeddingService._shared_model = None
                    EmbeddingService._shared_model_name = None
            return EmbeddingService._shared_model

    def _hash_embedding(self, text: str) -> List[float]:
        tokens = _TOKEN_RE.findall(text.lower())
        if not tokens:
            tokens = [text.lower()] if text else []
        values = [0.0] * self.embedding_dim
        if not tokens:
            return values
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            idx = int.from_bytes(digest[:4], "big") % self.embedding_dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (digest[5] / 255.0)
            values[idx] += sign * weight
        return normalize_vector(values, dim=self.embedding_dim)

    def _embed_sync(self, text: str) -> List[float]:
        normalized = self._normalized_text(text)
        if not normalized:
            return [0.0] * self.embedding_dim
        cache_key = self._cache_key(normalized)
        with self._cache_lock:
            cached = self._memory_cache.get(cache_key)
        if cached is not None:
            return list(cached)

        model = self._get_model()
        if model is not None:
            try:
                raw = model.encode(
                    [normalized],
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                )
                vector = normalize_vector(raw[0].tolist(), dim=self.embedding_dim)
            except Exception as exc:  # pragma: no cover - runtime model failure
                logger.warning("Embedding inference failed; using hashing fallback: %s", exc)
                vector = self._hash_embedding(normalized)
        else:
            vector = self._hash_embedding(normalized)

        with self._cache_lock:
            if len(self._memory_cache) >= 4000:
                # Deterministic, low-overhead eviction.
                oldest_key = next(iter(self._memory_cache))
                self._memory_cache.pop(oldest_key, None)
            self._memory_cache[cache_key] = list(vector)
        return vector

    async def embed(self, text: str) -> List[float]:
        return await asyncio.to_thread(self._embed_sync, text)

    async def batch_embed(self, texts: Sequence[str]) -> List[List[float]]:
        normalized_inputs = [self._normalized_text(text) for text in texts]
        if not normalized_inputs:
            return []

        model = self._get_model()
        if model is not None:
            uncached_index_to_text: Dict[int, str] = {}
            outputs: List[List[float] | None] = [None] * len(normalized_inputs)
            for idx, item in enumerate(normalized_inputs):
                if not item:
                    outputs[idx] = [0.0] * self.embedding_dim
                    continue
                key = self._cache_key(item)
                with self._cache_lock:
                    cached = self._memory_cache.get(key)
                if cached is not None:
                    outputs[idx] = list(cached)
                else:
                    uncached_index_to_text[idx] = item

            if uncached_index_to_text:
                batch_items = [uncached_index_to_text[idx] for idx in uncached_index_to_text]
                try:
                    raw_vectors = await asyncio.to_thread(
                        model.encode,
                        batch_items,
                        convert_to_numpy=True,
                        normalize_embeddings=True,
                    )
                    for raw_idx, vec in enumerate(raw_vectors):
                        original_idx = list(uncached_index_to_text.keys())[raw_idx]
                        normalized_vec = normalize_vector(vec.tolist(), dim=self.embedding_dim)
                        outputs[original_idx] = normalized_vec
                        with self._cache_lock:
                            if len(self._memory_cache) >= 4000:
                                self._memory_cache.pop(next(iter(self._memory_cache)), None)
                            self._memory_cache[self._cache_key(uncached_index_to_text[original_idx])] = list(
                                normalized_vec
                            )
                except Exception as exc:  # pragma: no cover - runtime model failure
                    logger.warning(
                        "Batch embedding inference failed; using hashing fallback: %s", exc
                    )

            if all(vector is not None for vector in outputs):
                return [list(vector or []) for vector in outputs]

        return [await self.embed(item) for item in normalized_inputs]
