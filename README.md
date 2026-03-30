# Soyog AI

Soyog AI is an AI-native research workspace for searching, synthesizing, and analyzing scientific literature at scale.

## Live Deployment

- Production frontend: <https://research-hub-ai-lime.vercel.app>
- Production backend docs: <https://soyog-ai-backend-568566718388.us-central1.run.app/docs>

## Platform Highlights

### Core product

- FastAPI backend with modular routes for auth, papers, chat, workspaces, AI, analytics, compliance, health checks, and the research agent.
- React + Vite + TypeScript frontend built around a workspace-centric research workflow.
- Firebase-first runtime for request-path persistence with Firestore and Firebase Storage.
- Legacy SQLAlchemy code retained for compatibility and migration workflows.

### AI and search

- Unified paper discovery across 28+ scholarly providers, including arXiv, NASA ADS, OpenAlex, and NCBI-backed sources.
- Groq-backed AI features for chat, PDF summarization, long-form synthesis, and mindmap/report generation.
- Per-feature model routing support through `GROQ_CHAT_MODEL`, `GROQ_UPLOAD_SUMMARY_MODEL`, `GROQ_MINDMAP_MODEL`, and `GROQ_PIPELINE_MODEL`.

### Production and operations

- Frontend deployed on Vercel and backend deployed on Google Cloud Run.
- Dynamic CORS handling for stable Vercel production and preview subdomains.
- Sentry error tracking, Prometheus-compatible metrics, health probes, structured logging, and production security headers.
- Backend build optimization via [`backend/.gcloudignore`](backend/.gcloudignore).

## Tech Stack

| Component | Technology |
| :-- | :-- |
| Frontend | React, TypeScript, Vite, Tailwind CSS, Axios |
| Backend | Python, FastAPI, Pydantic, Authlib |
| AI Models | Groq-hosted Llama 3.3 and DeepSeek R1 variants |
| Auth | Firebase Authentication, Google OAuth, email/password |
| Storage | Firestore, Firebase Storage, compatibility SQLAlchemy code |
| Hosting | Google Cloud Run, Vercel |
| Observability | Sentry, Prometheus metrics, Google Cloud Logging |

## Repository Layout

```text
ResearchHub-AI/
  backend/
    main.py
    routers/
    repositories/
    utils/
    tests/
  frontend/
    src/
  docs/
  ops/
  deploy/
```

## Local Setup

### Prerequisites

1. Python 3.11 or newer
2. Node.js 20 or newer
3. Google Cloud SDK with Firestore emulator support if you want to use `run_dev.ps1`
4. A Groq API key and Firebase project config for non-emulator or production-like runs

### 1. Create the local Python environment

Use the repository-root virtual environment. The workspace is already configured to prefer [`.vscode/settings.json`](.vscode/settings.json).

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r backend\requirements.txt
```

### 2. Configure environment files

Copy the shared example file into the backend and frontend folders:

```powershell
Copy-Item .env.example backend\.env
Copy-Item .env.example frontend\.env
```

Minimum values to review before running locally:

- `backend/.env`: `APP_ENV`, `SECRET_KEY`, `GROQ_API_KEY`, `FRONTEND_URL`
- `backend/.env`: Firebase settings such as `FIREBASE_PROJECT_ID`, `FIREBASE_CREDENTIALS_PATH`, and `FIREBASE_STORAGE_BUCKET` when not using the emulator
- `frontend/.env`: `VITE_API_URL` and the `VITE_FIREBASE_*` keys

Important runtime note:

- The active request-path backend is Firebase-first. For local development, either run against the Firestore emulator or provide real Firebase credentials.

### 3. Install frontend dependencies

```powershell
cd frontend
npm install
cd ..
```

### 4. Start the app

Recommended on Windows:

```powershell
.\run_dev.ps1
```

`run_dev.ps1` starts:

- the Firestore emulator on `localhost:8080`
- the backend on `http://localhost:8010`
- the frontend via Vite

Manual startup is also possible:

```powershell
# Terminal 1
gcloud beta emulators firestore start --project=studio-5606596663-2ca06 --host-port=localhost:8080

# Terminal 2
cd backend
$env:FIRESTORE_EMULATOR_HOST='localhost:8080'
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8010

# Terminal 3
cd frontend
npm run dev
```

## Common Commands

Backend tests with the Firestore emulator running:

```powershell
$env:FIRESTORE_EMULATOR_HOST='localhost:8080'
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

Frontend production build:

```powershell
cd frontend
npm run build
```

Optional Makefile shortcuts:

- `make start-backend`
- `make start-frontend`
- `make test`
- `make build-frontend`

## Additional Docs

- Deployment guide: [`DEPLOYMENT.md`](DEPLOYMENT.md)
- Monitoring guide: [`MONITORING.md`](MONITORING.md)
- Security guide: [`SECURITY.md`](SECURITY.md)
- Firebase runtime notes: [`docs/firebase-migration.md`](docs/firebase-migration.md)
- Edge deployment guide: [`docs/edge/global-edge-deployment.md`](docs/edge/global-edge-deployment.md)
- Disaster recovery plan: [`docs/resilience/backup-restore-dr-plan.md`](docs/resilience/backup-restore-dr-plan.md)

## Roadmap

- [ ] Add Pinecone or Weaviate-backed RAG retrieval
- [ ] Ship real-time collaboration for shared workspaces
- [ ] Expand report export formats to Markdown and LaTeX
- [ ] Improve full-text PDF parsing for non-open-access papers

## Maintainer

Maintained by Girish S. and the Soyog AI team.
