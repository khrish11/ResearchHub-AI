# Firebase Setup

Soyog AI uses Firebase as its primary backend infrastructure.

## Firebase Services Used

- **Firestore**: Primary database for all application data
- **Firebase Authentication**: User authentication and session management
- **Firebase Storage**: File storage for PDFs and workspace documents

## Environment Configuration

Configure these values in `backend/.env`:

```env
STORAGE_BACKEND=firebase
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_CREDENTIALS_PATH=path/to/service-account.json
FIREBASE_STORAGE_BUCKET=your-project-id.firebasestorage.app
FIREBASE_APPCHECK_ENFORCED=0  # Set to 1 in production
```

## Local Development

Use the Firebase emulators for local development:

```powershell
gcloud beta emulators firestore start --project=your-project-id --host-port=localhost:8081
```

The emulator configuration is in `firebase.json`.

## Security Rules

Security rules are defined in:
- `firestore.rules` - Firestore data access rules
- `storage.rules` - Firebase Storage access rules

## Collections

The following Firestore collections are used:
- `users` - User accounts
- `workspaces` - Research workspaces
- `papers` - Research papers
- `chats` - Chat conversations
- `search_history` - Search history
- `user_session_state` - Session state
- `workspace_documents` - Workspace documents
- `workspace_files` - Uploaded files
- `paper_check_jobs` - Paper analysis jobs
- And more as defined in the repository

For detailed historical migration information, see `docs/archive/reports/firebase-migration-historical.md`.
