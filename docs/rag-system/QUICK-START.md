# Workspace RAG Quick Start

## What was added
- Backend vector storage: `backend/repositories/vector_repository.py`
- Embeddings + chunking: `backend/services/embedding_service.py`
- Retrieval engine: `backend/services/retrieval_service.py`
- Grounded answer handler: `backend/services/rag_query_handler.py`
- Indexing service: `backend/services/rag_index_service.py`
- API routes: `backend/routers/rag.py`
- Frontend page: `frontend/src/pages/AskWorkspace.tsx`

## API flow
1. Index a workspace
```http
POST /api/rag/index/workspace
{
  "workspace_id": 123
}
```

2. Query retrieved context only
```http
GET /api/rag/retrieve?workspace_id=123&query=main%20trends&top_k=6
```

3. Ask grounded question
```http
POST /api/rag/query
{
  "workspace_id": 123,
  "query": "Which papers contradict each other?",
  "top_k": 6,
  "strict_grounding": true
}
```

## Environment knobs
- `RAG_EMBEDDING_PROVIDER=auto|hashing|sentence_transformers`
- `RAG_EMBEDDING_ALLOW_DOWNLOAD=0|1`
- `RAG_EMBEDDING_MODEL=all-MiniLM-L6-v2`
- `RAG_SIMILARITY_THRESHOLD=0.45`
- `RAG_MAX_CONTEXT_TOKENS=2200`
- `RAG_VECTOR_COLLECTION=workspace_vectors`

## Notes
- `RAG_EMBEDDING_ALLOW_DOWNLOAD=0` avoids runtime model downloads; if model is not cached locally, hashing fallback is used.
- Existing chat/compare/report features now add retrieved workspace context when vectors are available.
