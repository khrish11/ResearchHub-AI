# Database Schema

Soyog AI uses Firebase Firestore as its primary database.

## Collections

The following Firestore collections are used:

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

## Security

All Firestore collections are protected by comprehensive security rules defined in `firestore.rules`. The security model enforces:

- User isolation: Users can only access their own data
- Workspace isolation: Users can only access their own workspaces
- Backend-only writes: Most collections are write-restricted to backend operations

For detailed schema information, see `docs/firestore_schema.md`.
