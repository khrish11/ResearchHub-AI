# Firestore Schema Design — Soyog AI Research Platform

Optimized for a **read-heavy AI research workload** with flat collections, paginated queries, and no deep nesting.

---

## Collection Architecture

```
users/               ← user profiles
workspaces/          ← research workspaces (one per AI project)
papers/              ← saved research papers
chats/               ← AI conversation messages
search_history/      ← user query logs
session_states/      ← active UI session (current page/workspace)
workspace_documents/ ← rich-text notes and AI-generated drafts
workspace_files/     ← uploaded PDFs and attachments
data_rights_requests/ ← GDPR/CCPA requests
_counters/           ← monotonic ID shards (avoid hotspot writes)
```

---

## Collection Schemas

### `users/{user_id}`
```jsonc
{
  "id": 42,                          // integer, mirrors document ID
  "email": "alice@example.com",      // normalized lowercase
  "email_key": "alice@example.com",  // indexed, used for fast lookups
  "name": "Alice",
  "hashed_password": "...",          // bcrypt or null if Google-only
  "google_id": "108xxxxxxxx",        // nullable, unique
  "google_email": "alice@gmail.com", // nullable
  "profile_pic": "https://...",
  "is_active": true,
  "is_verified": true,
  "is_pro": false,                   // feature flag for future premium tier
  "created_at": "2026-01-01T00:00Z",
  "updated_at": "2026-01-01T00:00Z"
}
```
**Indexes needed:**
- `email_key` (ASC) — for login lookup
- `google_id` (ASC) — for OAuth callback

---

### `workspaces/{workspace_id}`
```jsonc
{
  "id": 1001,
  "user_id": 42,
  "name": "Transformer Architecture Study",
  "description": "Papers on attention mechanisms",
  "created_at": "2026-01-01T00:00Z"
}
```
**Indexes needed:**
- `user_id` (ASC) + `created_at` (DESC) — for paginated workspace list per user

---

### `papers/{paper_id}`
```jsonc
{
  "id": 5001,
  "workspace_id": 1001,
  "user_id": 42,
  "title": "Attention Is All You Need",
  "authors": "Vaswani et al.",
  "abstract": "We propose a novel model...",
  "url": "https://arxiv.org/abs/1706.03762",
  "doi": "10.48550/arXiv.1706.03762",
  "bibcode": null,
  "source": "arxiv",
  "pdf_url": "https://arxiv.org/pdf/1706.03762",
  "access_type": "open",
  "full_text_available": true
}
```
**Indexes needed:**
- `workspace_id` (ASC) + `user_id` (ASC) — for paper list per workspace
- `user_id` (ASC) + `source` (ASC) — for filtering by paper source

> ⚠️ **Size**: Avoid embedding full text in this document. Store it in `workspace_files` or a vector store reference instead.

---

### `chats/{chat_id}`
```jsonc
{
  "id": 9001,
  "workspace_id": 1001,
  "user_id": 42,
  "message": "Summarize the key contributions",
  "response": "The paper introduces...",
  "timestamp": "2026-01-01T10:00Z"
}
```
**Indexes needed:**
- `workspace_id` (ASC) + `timestamp` (DESC) — for paginated chat history

> 💡 **Pagination pattern**: Use cursor-based pagination with `timestamp` as the cursor field:
> ```python
> query = chats.where("workspace_id", "==", ws_id).order_by("timestamp", DESCENDING).start_after(cursor).limit(20)
> ```

---

### `search_history/{history_id}`
```jsonc
{
  "id": 7001,
  "user_id": 42,
  "query": "transformer self-attention",
  "source": "arxiv",
  "result_count": 35,
  "filters_json": "{\"year_from\": 2020}",
  "created_at": "2026-01-01T09:00Z"
}
```
**Indexes needed:**
- `user_id` (ASC) + `created_at` (DESC) — paginated query history per user

---

### `session_states/{session_id}`
```jsonc
{
  "id": 3001,
  "user_id": 42,
  "page_path": "/workspace/1001",
  "workspace_id": 1001,
  "last_query": "transformer attention",
  "draft_text": null,
  "extra_json": null,
  "updated_at": "2026-01-01T10:00Z"
}
```
**Indexes needed:**
- `user_id` (ASC) — single document per user, use `where("user_id", "==", uid).limit(1)`

> 💡 Alternative: use `session_states/user_{user_id}` as a deterministic document ID for O(1) access without a query.

---

### `workspace_documents/{doc_id}`
```jsonc
{
  "id": 2001,
  "workspace_id": 1001,
  "user_id": 42,
  "title": "Literature Review Draft",
  "content": "# Introduction\n...",  // Markdown or rich text, keep < 500KB
  "version": 3,
  "created_at": "2026-01-01T00:00Z",
  "updated_at": "2026-01-10T15:00Z"
}
```
> ⚠️ **1MB Limit**: If documents exceed ~500KB, split into `content_blocks` subcollection or use Cloud Storage + store URL only.

---

### `workspace_files/{file_id}`
```jsonc
{
  "id": 4001,
  "workspace_id": 1001,
  "user_id": 42,
  "kind": "pdf",
  "filename": "vaswani2017.pdf",
  "storage_bucket": "soyog-ai.firebasestorage.app",
  "storage_path": "uploads/user_42/vaswani2017.pdf",
  "content_type": "application/pdf",
  "size_bytes": 1048576,
  "download_url": "https://storage.googleapis.com/...",
  "paper_id": 5001,
  "created_at": "2026-01-01T00:00Z"
}
```

---

## Suggested `firestore.indexes.json`

```json
{
  "indexes": [
    {
      "collectionGroup": "workspaces",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "user_id", "order": "ASCENDING" },
        { "fieldPath": "created_at", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "papers",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "workspace_id", "order": "ASCENDING" },
        { "fieldPath": "user_id", "order": "ASCENDING" }
      ]
    },
    {
      "collectionGroup": "chats",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "workspace_id", "order": "ASCENDING" },
        { "fieldPath": "timestamp", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "search_history",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "user_id", "order": "ASCENDING" },
        { "fieldPath": "created_at", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "session_states",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "user_id", "order": "ASCENDING" }
      ]
    }
  ],
  "fieldOverrides": []
}
```

---

## Query Patterns

| Use Case | Query |
|---|---|
| Get workspace list | `workspaces.where("user_id","==",uid).order_by("created_at",DESC).limit(20)` |
| Get papers in workspace | `papers.where("workspace_id","==",wid).where("user_id","==",uid)` |
| Paginated chat history | `chats.where("workspace_id","==",wid).order_by("timestamp",DESC).start_after(cursor).limit(20)` |
| Latest session state | `session_states.where("user_id","==",uid).limit(1)` |
| User by email | `users.where("email_key","==",normalized_email).limit(1)` |

---

## Cost Optimization Tips

1. **Use document IDs as lookup keys** for session states (`session_states/user_{uid}`) to avoid index reads.
2. **Cache workspace lists** in memory per request — avoids repeated Firestore reads within a single API call.
3. **Paginate aggressively** — never stream entire collections. Use `.limit(50)` + cursor.
4. **Avoid `collection_group` queries** unless truly needed — prefer scoped queries with `workspace_id` + `user_id` filters.
5. **TTL for search_history** — delete entries older than 90 days via a scheduled Cloud Function or Firestore TTL policy.
6. **Shard `_counters`** — the current `_next_id` counter uses a single document; this becomes a write bottleneck above ~1 write/sec. Consider switching to Firestore's `FieldValue.increment()` with auto-generated IDs + externally persisted ID mapping.
