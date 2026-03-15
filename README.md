# Soyog AI

Soyog AI is an end-to-end research workspace where users can:

1. Search papers across multiple scholarly sources.
2. Import selected papers into personal workspaces.
3. Ask AI questions using workspace paper context.
4. Upload PDFs and auto-generate summaries.
5. Export literature synthesis and mindmap reports (PDF/DOCX).

## Key Features

1. Unified paper discovery (`/papers/search-global`) across 28+ providers.
2. Account system with email/password and Google OAuth login.
3. Workspace-centric organization for papers and AI chat history.
4. AI analysis modes (`summaries`, `insights`, `review`) with long-form output support.
5. Research report export with structured sections and mindmap block.
6. CSV/BibTeX workspace export for citations and external tooling.

## Tech Stack

1. Frontend: React, TypeScript, Vite, Tailwind, Axios, React Router.
2. Backend: FastAPI, SQLAlchemy, Pydantic, Authlib, PyJWT.
3. AI: Groq API (Llama model family).
4. Database: SQLite by default (configurable via `DATABASE_URL`).
5. Testing/CI: Pytest + GitHub Actions workflow (`.github/workflows/ci.yml`).

## Project Structure

```text
<repo-root>/
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
cd <repo-folder>
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
cd frontend
npm ci
cd ..
```

Development standard:

1. The supported local Python environment for this repo is `.venv` at the repository root.
2. Do not point your editor at `backend\venv`. If that folder exists on your machine, treat it as legacy local state.
3. VS Code/Windsurf will use the repo-tracked workspace setting in `.vscode/settings.json` to select `.venv`.

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
6. `STORAGE_BACKEND=sqlalchemy` (keep this value unless you are intentionally testing the Firebase-backed repository slice)
7. Keep `BACKEND_URL`, `VITE_API_URL`, and `GOOGLE_REDIRECT_URI` aligned with the actual backend port (`8010` in the commands below).
8. Leave `TRUST_PROXY_HEADERS=0` unless the app is running behind a reverse proxy you control and `TRUSTED_PROXY_IPS` is set correctly.

Optional AI routing values:

1. `GROQ_CHAT_MODEL`
2. `GROQ_UPLOAD_SUMMARY_MODEL`
3. `GROQ_MINDMAP_MODEL`
4. `GROQ_PIPELINE_MODEL`

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

### Python interpreter note

If VS Code or Windsurf keeps prompting you to select a Python interpreter:

1. Run `Python: Clear Workspace Interpreter Setting`.
2. Run `Developer: Reload Window`.
3. Select `${workspaceFolder}\\.venv\\Scripts\\python.exe` if prompted.
4. Confirm the status bar shows `.venv`.

Optional cleanup after `.venv` is working:

```powershell
Remove-Item -Recurse -Force backend\venv
```

Verification:

```powershell
python -V
python -c "import sys; print(sys.executable)"
```

## AI Model Routing

Soyog AI can now route different features to different Groq models:

1. `Chat`
2. `Upload Summary`
3. `Mindmap / Report`
4. `Pipeline / Agent`

Use `Settings -> AI model routing` to keep a lighter model on chat and a stronger model on long-form generation.

## Database Direction

Soyog AI now supports a full request-path Firebase runtime:

1. Firestore for users, workspaces, papers, chats, search history, session state, compliance requests, and developer/admin reads
2. Firebase Storage for uploaded PDFs and generated export/report files
3. `STORAGE_BACKEND=firebase` switches the active runtime persistence layer to Firebase
4. SQLAlchemy remains available as a compatibility fallback and migration source

Required Firebase envs are documented in `.env.example` and the operational details live in `docs/firebase-migration.md`.

### Alembic migrations (SQLAlchemy mode)

When `STORAGE_BACKEND=sqlalchemy`, apply schema changes with Alembic:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

If an existing local database already matches the baseline and you only want to mark it:

```powershell
.\.venv\Scripts\python.exe -m alembic stamp head
```

### SQL to Firebase migration script

Dry run first:

```powershell
.\.venv\Scripts\python.exe backend\scripts\migrate_sql_to_firebase.py --dry-run
```

Real migration after setting `FIREBASE_PROJECT_ID` and `FIREBASE_CREDENTIALS_PATH`:

```powershell
.\.venv\Scripts\python.exe backend\scripts\migrate_sql_to_firebase.py --drop-target
```

The executable path should point to `.venv`.

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

### Frontend E2E smoke tests

```powershell
cd frontend
npx playwright install
npm run test:e2e
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
4. Install local pre-push secret guard:
   ```powershell
   .\scripts\install-git-hooks.ps1
   ```

## Production Hardening

1. Built-in API rate limiting is configurable with:
   `RATE_LIMIT_ENABLED`, `RATE_LIMIT_WINDOW_SECONDS`, `RATE_LIMIT_AUTH_PER_WINDOW`, `RATE_LIMIT_API_PER_WINDOW`.
2. Optional Redis-backed limiter:
   `RATE_LIMIT_STORE=redis` with `REDIS_URL=redis://...`.
3. Cookie auth controls:
   `AUTH_COOKIE_SAMESITE`, `AUTH_COOKIE_DOMAIN`, `AUTH_COOKIE_SECURE`.
4. Security headers can be toggled with `SECURITY_HEADERS_ENABLED`.
5. Health probes:
   - Liveness: `GET /health/live`
   - Readiness (DB check): `GET /health/ready`

## External Security Testing

1. Automated security workflow: `.github/workflows/security-scans.yml`
2. Secret scan workflow: `.github/workflows/secret-scan.yml`
3. OWASP ZAP local scan:
   ```powershell
   .\scripts\run_owasp_zap.ps1 -TargetUrl https://app.example.com
   ```
4. Manual penetration testing playbook:
   - `docs/security/penetration-testing-playbook.md`
   - `docs/security/owasp-scan-operations.md`
5. Dependency update automation: `.github/dependabot.yml`

## Production Edge Setup

1. Nginx reverse-proxy baseline: `deploy/nginx/researchhub.conf`
2. Cloudflare rules template: `deploy/cloudflare/waf-rules.json`
3. Edge deployment guide: `docs/edge/global-edge-deployment.md`

## Observability and SRE

1. Prometheus scrape endpoint: `GET /ops/metrics` (supports optional `X-Metrics-Token`)
2. SLO endpoint: `GET /ops/slo`
3. Monitoring configs:
   - `ops/monitoring/prometheus.yml`
   - `ops/monitoring/alerts.yml`
4. Runbooks:
   - `ops/runbooks/incident-response.md`
   - `ops/runbooks/slo-policy.md`

## Data Resilience

1. Backup:
   ```powershell
   python scripts/db_backup.py --out-dir backups
   ```
2. Restore:
   ```powershell
   python scripts/db_restore.py --backup-file backups/<file> --manifest-file backups/<manifest> --force
   ```
3. Disaster-recovery drill:
   ```powershell
   python scripts/backup_restore_drill.py
   ```
4. CI drill workflow: `.github/workflows/dr-backup-restore-drill.yml`
5. DR plan: `docs/resilience/backup-restore-dr-plan.md`

## Compliance and Legal

1. Public legal pages:
   - `/privacy`
   - `/terms`
   - `/cookies`
   - `/data-rights`
2. Data rights API:
   - `POST /compliance/data-rights-request`
   - `GET /compliance/data-rights-request/me`
   - `GET /compliance/export-my-data`

## Accessibility (WCAG 2.2 AA)

1. Automated audit:
   ```powershell
   cd frontend
   npm run build
   npm run a11y:ci
   ```
2. Audit config: `frontend/.pa11yci.json`
3. CI audit workflow: `.github/workflows/accessibility-audit.yml`
4. Manual checklist: `docs/accessibility/wcag-2.2-aa-audit-checklist.md`

## License

Add your preferred license here (MIT/Apache-2.0/etc.).
