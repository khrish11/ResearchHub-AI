# ResearchHub-AI

> Local research assistant — search, import papers, chat with your paper collections.

[![CI](https://github.com/<YOUR-ORG>/<YOUR-REPO>/actions/workflows/ci.yml/badge.svg)](https://github.com/<YOUR-ORG>/<YOUR-REPO>/actions/workflows/ci.yml)  
*(Replace <YOUR-ORG>/<YOUR-REPO> with your GitHub repository path to enable the badge.)*

## Quick start (development)

Requirements: Python 3.11+, Node 20+, npm, and an OS-supported Python build toolchain for optional native packages.

Backend (API)

- Create & activate virtualenv: `python -m venv .venv` then `.venv\Scripts\activate` (Windows PowerShell)
- Install: `pip install -r backend/requirements.txt`
- Create `.env` (there is an example `.env` in the repo). Important values:
  - `GROQ_API_KEY` (optional, enables AI chat)
  - `SECRET_KEY` (JWT secret)
  - `USE_BCRYPT=1` to opt-in to bcrypt hashing (portable default is `pbkdf2_sha256`)
- Run dev server: `cd backend && .venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000`

Frontend (UI)

- Install: `cd frontend && npm ci`
- Run dev server: `npm run dev` (Vite will print the local URL)
- Build for production: `npm run build`

Tests

- Run backend tests: `cd backend && .venv\Scripts\python.exe -m pytest -q`

Developer convenience (Makefile)

- `make start-backend` — start backend dev server
- `make start-frontend` — start frontend dev server
- `make test` — run backend tests
- `make build-frontend` — build frontend for production

(Windows users may prefer the PowerShell helper `run_dev.ps1` in the repo root.)

## Bcrypt & password hashing

- The app defaults to `pbkdf2_sha256` which is portable and avoids platform-specific bcrypt issues.
- To enable `bcrypt` hashing set `USE_BCRYPT=1` in your `.env` and ensure the `bcrypt` Python package is installed on your target host.
- The code falls back to `pbkdf2_sha256` if bcrypt isn't available at runtime.

## CI

- A GitHub Actions workflow is included at `.github/workflows/ci.yml` — it runs backend pytest and builds the frontend on push/PR.
- Add the Actions badge above by replacing the repository path.

## Notes

- If you plan to run AI features, set `GROQ_API_KEY` in `.env`.
- The app uses a local SQLite DB by default (`researchhub.db`) — switch to Postgres for production.

---

If you'd like, I can open a PR with these changes and add more CI checks (coverage, linting, deploy). Which next? (I recommend enabling CI checks first — I already added the workflow.)