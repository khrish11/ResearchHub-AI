# ResearchHub-AI

ResearchHub-AI is an end-to-end research workspace where users can:

1. Search papers across multiple scholarly sources.
2. Import selected papers into personal workspaces.
3. Ask AI questions using workspace paper context.
4. Upload PDFs and auto-generate summaries.
5. Export literature synthesis and mindmap reports (PDF/DOCX).

## Key Features

1. Unified paper discovery (`/papers/search-global`) across 14+ providers.
2. Account system with email/password and Google OAuth login.
3. Workspace-centric organization for papers and AI chat history.
4. AI analysis modes (`summaries`, `insights`, `review`) with long-form output support.
5. Research report export with structured sections and mindmap block.
6. CSV/BibTeX workspace export for citations and external tooling.

## Tech Stack

1. Frontend: React, TypeScript, Vite, Tailwind, Axios, React Router.
2. Backend: FastAPI, SQLAlchemy, Pydantic, Authlib, python-jose.
3. AI: Groq API (Llama model family).
4. Database: SQLite by default (configurable via `DATABASE_URL`).
5. Testing/CI: Pytest + GitHub Actions workflow (`.github/workflows/ci.yml`).

## Project Structure

```text
ResearchHub-AI/
  backend/
    main.py
    database.py
    models.py
    routers/
    utils/
    tests/
  frontend/
    src/
      pages/
      components/
      utils/
```

## Quick Start (Development)

### Prerequisites

1. Python 3.11+
2. Node.js 20+ and npm
3. Git

### 1) Clone and install dependencies

```powershell
git clone <your-repo-url>
cd ResearchHub-AI
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
cd frontend
npm ci
cd ..
```

### 2) Configure environment files

Copy the example file and fill real values:

```powershell
copy .env.example backend\.env
copy .env.example frontend\.env
```

Minimum required backend values:

1. `SECRET_KEY`
2. `BACKEND_URL`
3. `FRONTEND_URL`
4. `DATABASE_URL` (optional if default SQLite is used)
5. `GROQ_API_KEY` (required for AI features)

Frontend value:

1. `VITE_API_URL` (must match backend URL)

### 3) Run backend and frontend

Option A: Use helper script (Windows):

```powershell
.\run_dev.ps1
```

Option B: Run manually in two terminals:

Terminal 1 (backend):

```powershell
cd backend
python -m uvicorn main:app --reload --port 8010
```

Terminal 2 (frontend):

```powershell
cd frontend
npm run dev
```

Open the frontend URL printed by Vite (usually `http://localhost:5173`).

## Common Commands

### Backend tests

```powershell
python -m pytest backend/tests -q
```

### Frontend production build

```powershell
cd frontend
npm run build
```

### Makefile shortcuts (if using make)

1. `make start-backend`
2. `make start-frontend`
3. `make test`
4. `make build-frontend`

## Notes

1. Default local DB is `backend/researchhub.db`.
2. AI endpoints return graceful errors if `GROQ_API_KEY` is missing.
3. Google OAuth requires correct redirect URI in Google Console and `backend/.env`.
4. Never commit real secrets in `.env` files.

## Security and Secret Hygiene

1. Keep only placeholders in `.env.example`.
2. Store real keys only in local `.env` files or secret managers.
3. Rotate any key that was accidentally exposed.

## License

Add your preferred license here (MIT/Apache-2.0/etc.).
