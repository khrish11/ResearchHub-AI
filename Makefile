# Makefile for common dev tasks (Linux/WSL/macOS). On Windows use PowerShell or the provided scripts.
PYTHON=.venv/Scripts/python.exe
NPM=npm

.PHONY: start-backend start-frontend test build-frontend lint

start-backend:
	cd backend && $(PYTHON) -m uvicorn main:app --reload --port 8000

start-frontend:
	cd frontend && $(NPM) run dev

test:
	cd backend && $(PYTHON) -m pytest -q

build-frontend:
	cd frontend && $(NPM) run build

lint:
	cd frontend && $(NPM) run lint || true

clean:  # remove generated files (safe)
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path .\\scripts\\cleanup-workspace.ps1) { .\\scripts\\cleanup-workspace.ps1 } else { Write-Output 'Run scripts/cleanup-workspace.ps1 to clean workspace' }" || true
	@rm -rf frontend/dist || true
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@find backend/tests -name 'test_temp*.db' -delete 2>/dev/null || true
