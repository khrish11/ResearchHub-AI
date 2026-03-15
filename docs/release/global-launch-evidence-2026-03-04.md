# Global Launch Evidence Log

Date: 2026-03-04  
Environment: local verification on `<repo-root>`  
Assessor: Codex
Updated at: 2026-03-05 20:03:49 +05:30

Legend: `PASS` | `PARTIAL` | `BLOCKED`

## 1) External Security Testing
Status: `BLOCKED`

Evidence collected:
- Internal automation exists:
  - `.github/workflows/security-scans.yml`
  - `.github/workflows/secret-scan.yml`
  - `.github/dependabot.yml`
  - `docs/security/penetration-testing-playbook.md`
  - `docs/security/owasp-scan-operations.md`
  - `SECURITY.md`
- Local security scans executed:
  - `bandit -r backend -x backend/tests,backend/venv,... -ll`
    - result: 14 findings (`0 high`, `3 medium`, `11 low`)
  - `pip-audit -r backend/requirements.txt`
    - after dependency updates (`python-multipart==0.0.22`, `PyJWT[crypto]>=2.10.1`): `No known vulnerabilities found`
  - `npm audit --omit=dev`
    - result: `0 vulnerabilities`

Missing for `PASS`:
- External penetration test report from third-party tester.
- OWASP ZAP scan artifact against public production URL.

## 2) Production Edge Security
Status: `BLOCKED`

Evidence collected:
- Edge config templates exist:
  - `deploy/nginx/researchhub.conf`
  - `deploy/cloudflare/waf-rules.json`
  - `docs/edge/global-edge-deployment.md`

Missing for `PASS`:
- Live production proof of WAF/CDN/TLS/HSTS/DDoS on public domain.

## 3) Observability and SRE
Status: `PARTIAL`

Evidence collected:
- Runbooks/configs present:
  - `ops/runbooks/slo-policy.md`
  - `ops/runbooks/incident-response.md`
  - `ops/monitoring/prometheus.yml`
  - `ops/monitoring/alerts.yml`
- Endpoint coverage validated in backend test suite (`40 passed` total across endpoint/additional tests).
- Runtime note on currently running service at `127.0.0.1:8010`:
  - `/` responded with `{"message":"Soyog AI API is running"}`
  - `/health/live` and `/health/ready` returned `404` on that process, indicating deployment/runtime drift versus current code.

Missing for `PASS`:
- 30+ days of production uptime/SLO dashboard evidence.
- Runtime deployment must match current hardened backend build.

## 4) Data Resilience and DR
Status: `PARTIAL`

Evidence collected:
- Backup/restore/drill scripts and workflow exist:
  - `scripts/db_backup.py`
  - `scripts/db_restore.py`
  - `scripts/backup_restore_drill.py`
  - `.github/workflows/dr-backup-restore-drill.yml`
  - `docs/resilience/backup-restore-dr-plan.md`
- Local drill executed:
  - `python scripts/backup_restore_drill.py`
  - result: `status=ok`, `restored_rows=3`

Missing for `PASS`:
- Production backup schedule/export proof.
- Monthly full-environment DR rehearsal evidence.

## 5) Compliance and Legal
Status: `PARTIAL`

Evidence collected:
- Legal pages implemented:
  - `frontend/src/pages/PrivacyPolicy.tsx`
  - `frontend/src/pages/TermsOfService.tsx`
  - `frontend/src/pages/CookiePolicy.tsx`
  - `frontend/src/pages/DataRights.tsx`
- Compliance/data-rights API implemented:
  - `backend/routers/compliance.py`
- Compliance API flow validated in tests:
  - create data-rights request
  - list own requests
  - export user data payload

Missing for `PASS`:
- Counsel/legal sign-off for jurisdictions and production language.

## 6) Accessibility (WCAG 2.2 AA)
Status: `PARTIAL`

Evidence collected:
- Automated audit flow exists:
  - `.github/workflows/accessibility-audit.yml`
  - `frontend/.pa11yci.json`
  - `docs/accessibility/wcag-2.2-aa-audit-checklist.md`
- Local automation executed:
  - `npm run a11y:ci`
  - result: `7/7 URLs passed`

Missing for `PASS`:
- Signed manual screen-reader + keyboard audit evidence.

## 7) Functional Smoke (Import/Resolve/Filter)
Status: `PASS` (local smoke)

Evidence collected:
- Live backend smoke executed against `http://127.0.0.1:8010`:
  - `POST /auth/register` => `200`
  - `POST /workspaces/` => `200`
  - `POST /papers/import` (metadata paper) => `200`
  - `POST /papers/import` (paper with direct pdf) => `200`
  - `POST /papers/resolve-access` => `200`
  - `GET /workspaces/{id}` => `200`
  - `GET /papers/search-global?...` => `200`
- Captured smoke summary:
  - `workspace_paper_count=2`
  - `workspace_full_text_count=2`
  - `search_total_results=20`
  - `search_filtered_openalex_or_arxiv=1`
  - `flow_pass=true`
- Frontend live startup check:
  - temporary dev server at `http://127.0.0.1:5174`
  - `/` => `200`, `/login` => `200`

## Local Verification Commands
Executed:
- Backend:
  - `python -m pytest backend/tests/test_endpoints.py backend/tests/test_additional.py`
  - result: `40 passed`
- Frontend:
  - `npm run lint` => pass
  - `npm run build` => pass
  - `npm run a11y:ci` => pass (`7/7`)
- Security:
  - `bandit ... -ll` => findings present (no high)
  - `pip-audit ...` => no known vulnerabilities
  - `npm audit --omit=dev` => `0 vulnerabilities`
- DR:
  - `python scripts/backup_restore_drill.py` => pass
- Live smoke:
  - import/resolve/filter flow => pass on backend `8010`

## Current Overall Verdict
`NOT GLOBAL-READY YET` (external production/legal/manual-audit evidence still required).
