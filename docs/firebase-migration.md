# Firebase Runtime Notes

Soyog AI now supports a Firebase-first runtime for its request-path persistence.

## Active runtime coverage

With `STORAGE_BACKEND=firebase`, the backend persists these areas through Firestore and Firebase Storage:

1. users and account profile changes
2. Google-linked account reconciliation
3. workspaces
4. papers
5. chats
6. search history
7. user session state
8. workspace documents
9. compliance data-rights requests
10. uploaded PDF file bytes and workspace/export file records
11. developer/admin read models

## Environment

Use these values in `backend/.env`:

```env
STORAGE_BACKEND=firebase
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_CREDENTIALS_PATH=E:/secrets/soyog-firebase-admin.json
FIREBASE_STORAGE_BUCKET=your-project-id.firebasestorage.app
```

You can use `GOOGLE_APPLICATION_CREDENTIALS` instead of `FIREBASE_CREDENTIALS_PATH`.

## Backfill existing SQL data

Dry run:

```powershell
.\.venv\Scripts\python.exe backend\scripts\migrate_sql_to_firebase.py --dry-run
```

Real migration:

```powershell
.\.venv\Scripts\python.exe backend\scripts\migrate_sql_to_firebase.py --drop-target
```

The migration script:

1. reads the SQLAlchemy source database
2. writes Firestore documents keyed by integer `id`
3. preserves collection counts
4. seeds `_counters` so new Firestore writes continue the existing IDs

## Runtime verification

After migration and config:

1. restart the backend
2. verify:
   - `GET /health/live`
   - `GET /health/ready`
3. exercise:
   - register/login
   - create workspace
   - upload PDF
   - open workspace
   - chat
   - export files
   - compliance export
4. confirm Firestore collections update:
   - `users`
   - `workspaces`
   - `papers`
   - `chats`
   - `search_history`
   - `user_session_state`
   - `workspace_documents`
   - `workspace_files`
   - `data_rights_requests`
   - `_counters`

## Compatibility notes

SQLAlchemy is still present for:

1. local compatibility fallback when `STORAGE_BACKEND=sqlalchemy`
2. migration-source reads
3. legacy helper code that is no longer on the active request path

It is no longer the primary runtime path once `STORAGE_BACKEND=firebase` is enabled.
