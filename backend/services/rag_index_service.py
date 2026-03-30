from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict, List, Sequence

from google.cloud.firestore_v1.base_query import FieldFilter

from repositories.research import ResearchRepository
from repositories.vector_repository import VectorDocument, VectorStore
from services.embedding_service import EmbeddingService, chunk_text


@dataclass
class IndexStats:
    indexed_vectors: int = 0
    indexed_sources: int = 0
    by_type: Dict[str, int] | None = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "indexed_vectors": int(self.indexed_vectors),
            "indexed_sources": int(self.indexed_sources),
            "by_type": dict(self.by_type or {}),
        }


class RAGIndexService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
    ) -> None:
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    @staticmethod
    def _vector_id(
        *,
        workspace_id: int,
        source_id: str,
        source_type: str,
        chunk_idx: int,
        chunk_text_value: str,
    ) -> str:
        digest = sha256(
            f"{workspace_id}|{source_id}|{source_type}|{chunk_idx}|{chunk_text_value}".encode(
                "utf-8"
            )
        ).hexdigest()[:24]
        return f"vec_{workspace_id}_{source_type}_{source_id}_{chunk_idx}_{digest}"

    async def index_source(
        self,
        *,
        workspace_id: int,
        source_id: str,
        source_type: str,
        text: str,
        metadata: Dict[str, Any] | None = None,
    ) -> int:
        content = str(text or "").strip()
        if not content:
            return 0
        normalized_type = str(source_type or "unknown").strip().lower() or "unknown"
        chunks = chunk_text(content)
        if not chunks:
            return 0
        embeddings = await self.embedding_service.batch_embed(chunks)
        await self.vector_store.delete_by_source(
            workspace_id=int(workspace_id),
            source_id=str(source_id),
            source_type=normalized_type,
        )
        now = datetime.now(timezone.utc)
        docs: List[VectorDocument] = []
        for idx, chunk in enumerate(chunks):
            embedding = embeddings[idx] if idx < len(embeddings) else []
            docs.append(
                VectorDocument(
                    id=self._vector_id(
                        workspace_id=int(workspace_id),
                        source_id=str(source_id),
                        source_type=normalized_type,
                        chunk_idx=idx,
                        chunk_text_value=chunk,
                    ),
                    workspace_id=int(workspace_id),
                    source_id=str(source_id),
                    source_type=normalized_type,
                    text=chunk,
                    embedding=[float(value) for value in embedding],
                    chunk_index=idx,
                    metadata=dict(metadata or {}),
                    created_at=now,
                    updated_at=now,
                )
            )
        await self.vector_store.upsert_many(docs)
        return len(docs)

    async def index_paper_record(self, paper: Any) -> int:
        workspace_id = int(getattr(paper, "workspace_id", 0) or 0)
        paper_id = int(getattr(paper, "id", 0) or 0)
        if workspace_id <= 0 or paper_id <= 0:
            return 0
        text = "\n".join(
            [
                f"Title: {getattr(paper, 'title', '')}",
                f"Authors: {getattr(paper, 'authors', '')}",
                f"Abstract: {getattr(paper, 'abstract', '')}",
                f"DOI: {getattr(paper, 'doi', '') or ''}",
                f"URL: {getattr(paper, 'url', '') or ''}",
            ]
        )
        return await self.index_source(
            workspace_id=workspace_id,
            source_id=str(paper_id),
            source_type="paper",
            text=text,
            metadata={
                "title": getattr(paper, "title", None),
                "authors": getattr(paper, "authors", None),
                "doi": getattr(paper, "doi", None),
                "url": getattr(paper, "url", None),
            },
        )

    async def index_workspace(
        self,
        *,
        repo: ResearchRepository,
        workspace_id: int,
        user_id: int,
    ) -> IndexStats:
        stats = IndexStats(indexed_vectors=0, indexed_sources=0, by_type={})
        papers = repo.list_papers_for_workspace(int(workspace_id))
        paper_ids = {int(paper.id) for paper in papers}
        for paper in papers:
            count = await self.index_paper_record(paper)
            if count > 0:
                stats.indexed_sources += 1
                stats.indexed_vectors += count
                stats.by_type["paper"] = int(stats.by_type.get("paper", 0)) + count

        document = repo.get_docspace_document(int(workspace_id), int(user_id))
        if document and str(document.content or "").strip():
            count = await self.index_source(
                workspace_id=workspace_id,
                source_id=f"docspace_{workspace_id}",
                source_type="summary",
                text=document.content,
                metadata={"title": document.title, "document_id": document.id},
            )
            if count > 0:
                stats.indexed_sources += 1
                stats.indexed_vectors += count
                stats.by_type["summary"] = int(stats.by_type.get("summary", 0)) + count

        db = getattr(repo, "db", None)
        if db is not None:
            try:
                checker_rows = list(
                    db.collection("paper_check_jobs")
                    .where(filter=FieldFilter("status", "==", "completed"))
                    .where(filter=FieldFilter("user_id", "==", int(user_id)))
                    .stream()
                )
            except Exception:
                checker_rows = []
            for row in checker_rows:
                payload = row.to_dict() or {}
                job_workspace_raw = (
                    (payload.get("input_data") or {}).get("workspace_id")
                    if isinstance(payload.get("input_data"), dict)
                    else None
                )
                try:
                    job_workspace = int(job_workspace_raw) if job_workspace_raw is not None else None
                except Exception:
                    job_workspace = None
                paper_id = payload.get("paper_id")
                if job_workspace != int(workspace_id) and int(paper_id or 0) not in paper_ids:
                    continue
                result_blob = payload.get("result")
                if not result_blob:
                    continue
                text = json.dumps(result_blob, ensure_ascii=False)
                count = await self.index_source(
                    workspace_id=workspace_id,
                    source_id=str(payload.get("job_id") or row.id),
                    source_type="checker",
                    text=text,
                    metadata={"paper_id": paper_id, "title": f"Paper check {paper_id or ''}".strip()},
                )
                if count > 0:
                    stats.indexed_sources += 1
                    stats.indexed_vectors += count
                    stats.by_type["checker"] = int(stats.by_type.get("checker", 0)) + count

            try:
                report_rows = list(
                    db.collection("research_reports")
                    .where(filter=FieldFilter("user_id", "==", int(user_id)))
                    .stream()
                )
            except Exception:
                report_rows = []
            for row in report_rows:
                payload = row.to_dict() or {}
                report_paper_ids = {
                    int(value)
                    for value in (payload.get("paper_ids") or [])
                    if str(value).isdigit()
                }
                if report_paper_ids and report_paper_ids.isdisjoint(paper_ids):
                    continue
                result_blob = payload.get("result")
                if not result_blob:
                    continue
                text = json.dumps(result_blob, ensure_ascii=False)
                count = await self.index_source(
                    workspace_id=workspace_id,
                    source_id=str(payload.get("id") or row.id),
                    source_type="report",
                    text=text,
                    metadata={"title": str(payload.get("topic") or "Research report")},
                )
                if count > 0:
                    stats.indexed_sources += 1
                    stats.indexed_vectors += count
                    stats.by_type["report"] = int(stats.by_type.get("report", 0)) + count

        return stats

    async def index_ad_hoc_items(
        self,
        *,
        workspace_id: int,
        items: Sequence[Dict[str, Any]],
    ) -> IndexStats:
        stats = IndexStats(indexed_vectors=0, indexed_sources=0, by_type={})
        for item in items:
            source_id = str(item.get("source_id") or "").strip()
            source_type = str(item.get("source_type") or "unknown").strip().lower()
            text = str(item.get("text") or "").strip()
            if not source_id or not text:
                continue
            count = await self.index_source(
                workspace_id=workspace_id,
                source_id=source_id,
                source_type=source_type,
                text=text,
                metadata=dict(item.get("metadata") or {}),
            )
            if count <= 0:
                continue
            stats.indexed_sources += 1
            stats.indexed_vectors += count
            stats.by_type[source_type] = int(stats.by_type.get(source_type, 0)) + count
        return stats
