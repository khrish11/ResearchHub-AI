# Global Launch Readiness Gate

Last updated: 2026-03-04
Owner: Engineering + Security + SRE + Legal

This gate is strict: production launch is **blocked** until all required controls are `PASS`.

## Verdict Rules
- `PASS`: all mandatory checks in a control are complete with timestamped evidence.
- `PARTIAL`: some checks pass, but one or more mandatory checks are missing.
- `BLOCKED`: control cannot be validated from code-only/local context and has no external evidence attached.
- Final launch verdict: `PASS` only if every required control is `PASS`.

## 1) External Security Testing (Required)
Mandatory checks:
- OWASP ZAP baseline run against public production URL with report artifact.
- Manual penetration test report from an external security tester (scope, findings, CVSS, retest status).
- No unresolved `Critical` or `High` vulnerabilities without approved waiver and remediation date.

Evidence:
- `.github/workflows/security-scans.yml`
- `docs/security/penetration-testing-playbook.md`
- `docs/security/owasp-scan-operations.md`
- Release artifact links to latest reports

## 2) Production Edge Security (Required)
Mandatory checks:
- CDN/WAF enabled on production hostname.
- TLS 1.2+ enforced with valid certificate chain.
- HSTS enabled with `max-age >= 31536000`, `includeSubDomains`, `preload`.
- DDoS protections enabled at edge provider.
- Origin firewall restricted to edge provider egress where possible.

Evidence:
- `deploy/nginx/researchhub.conf`
- `deploy/cloudflare/waf-rules.json`
- `docs/edge/global-edge-deployment.md`
- Screenshot/export evidence from edge provider + SSL test report

## 3) Observability and SRE (Required)
Mandatory checks:
- Health/readiness endpoints operational.
- Metrics endpoint operational and scraped.
- SLOs defined (availability + latency) and alerting rules configured.
- Incident response runbook exists and on-call workflow assigned.
- At least 30 days of uptime and alert evidence before global readiness claim.

Evidence:
- `backend/main.py` (`/health/live`, `/health/ready`, `/ops/slo`, `/ops/metrics`)
- `ops/monitoring/prometheus.yml`
- `ops/monitoring/alerts.yml`
- `ops/runbooks/slo-policy.md`
- `ops/runbooks/incident-response.md`
- Monitoring dashboard/export links

## 4) Data Resilience and DR (Required)
Mandatory checks:
- Automated backups scheduled.
- Restore script validated against recent backup artifact.
- Backup/restore drill executed and documented.
- DR plan defines RTO/RPO and failover workflow.
- Monthly full-environment DR rehearsal documented.

Evidence:
- `scripts/db_backup.py`
- `scripts/db_restore.py`
- `scripts/backup_restore_drill.py`
- `.github/workflows/dr-backup-restore-drill.yml`
- `docs/resilience/backup-restore-dr-plan.md`
- Latest drill logs/artifacts

## 5) Compliance and Legal (Required)
Mandatory checks:
- Privacy Policy, Terms of Service, Cookie Policy publicly available.
- Data rights workflows (access/export/delete/rectification request intake) functional.
- Jurisdiction review completed for target markets (at minimum GDPR/CCPA-style rights mapping).
- Legal sign-off captured for production text and data handling disclosures.

Evidence:
- `frontend/src/pages/PrivacyPolicy.tsx`
- `frontend/src/pages/TermsOfService.tsx`
- `frontend/src/pages/CookiePolicy.tsx`
- `frontend/src/pages/DataRights.tsx`
- `backend/routers/compliance.py`
- Legal approval record or ticket link

## 6) Accessibility (WCAG 2.2 AA) (Required)
Mandatory checks:
- Automated accessibility audit passes in CI.
- Manual keyboard-only navigation checks complete.
- Manual screen reader checks complete (NVDA/JAWS or VoiceOver equivalent).
- No unresolved critical accessibility issues; serious issues need waiver + due date.

Evidence:
- `.github/workflows/accessibility-audit.yml`
- `frontend/.pa11yci.json`
- `docs/accessibility/wcag-2.2-aa-audit-checklist.md`
- Manual audit notes and issue tracker links

## 7) Functional Smoke (Import/Resolve/Filter) (Required)
Mandatory checks:
- Backend and frontend run on launch configuration.
- End-to-end smoke test verifies:
  - paper import into workspace
  - access resolve flow
  - filter/search behavior returns expected narrowed result set
- Smoke evidence includes timestamp and API/UI output snippets.

Evidence:
- Runtime command log + captured responses
- `backend/routers/papers.py`
- `frontend/src/pages/SearchPapers.tsx`

## Release Decision
- Only declare "global-level ready" when Sections 1-7 are all `PASS` with attached evidence.
