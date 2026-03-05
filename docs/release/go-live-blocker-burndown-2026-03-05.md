# Go-Live Blocker Burn-Down

Date: 2026-03-05  
Scope: Global launch readiness  
Source baseline: `docs/release/global-launch-evidence-2026-03-04.md`

## Rollup
- Total blockers: `9`
- Critical blockers: `5`
- High blockers: `4`
- Local engineering verification: `PASS`
- External/production evidence status: `PENDING`
- Default internal owner: `ResearchHub Dev` (acting Eng/Sec/SRE lead)

## Blocker Board

| ID | Area | Severity | Current Status | Owner | Target Date | Exit Criteria | Evidence Required |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SEC-01 | External penetration test | Critical | In Progress | `ResearchHub Dev + External Pentest Vendor (to assign)` | `2026-03-26` | Independent pentest complete; no unresolved critical/high (or approved waiver) | Vendor report + retest report |
| SEC-02 | OWASP ZAP on public prod URL | High | In Progress | `ResearchHub Dev` | `2026-03-12` | Baseline scan executed on production host; findings triaged | ZAP artifact from workflow/manual run |
| SEC-03 | Remaining Python vulnerability (`ecdsa`) | High | Closed | `ResearchHub Dev` | `2026-03-05` | Migrate from `python-jose` to `PyJWT`; clean audit | `pip-audit -r backend/requirements.txt` (no known vulnerabilities) |
| EDGE-01 | WAF/CDN/TLS/HSTS/DDoS in production | Critical | In Progress | `ResearchHub Dev` | `2026-03-14` | Edge controls active and validated on public domain | Cloudflare/Nginx screenshots + SSL check report |
| OBS-01 | Runtime drift on backend `8010` | High | In Progress | `ResearchHub Dev` | `2026-03-08` | Running service exposes expected `/health/live` and `/health/ready` endpoints | Curl/web evidence from deployed process |
| OBS-02 | 30-day SLO evidence | Critical | Open | `ResearchHub Dev` | `2026-04-05` | 30+ days uptime/latency/error-budget evidence available | Monitoring dashboard export + alert history |
| DR-01 | Production backup schedule proof | High | In Progress | `ResearchHub Dev` | `2026-03-10` | Automated backups confirmed in production cadence | Scheduler config + backup logs |
| DR-02 | Monthly full-environment DR rehearsal | Critical | Open | `ResearchHub Dev` | `2026-03-21` | One full failover/recovery rehearsal completed and documented | Drill report with RTO/RPO actuals |
| LEG-01 | Legal sign-off (Privacy/Terms/Cookies/data rights) | Critical | Open | `External Counsel (to assign)` | `2026-03-24` | Counsel approval for target jurisdictions and policy language | Approved legal ticket/doc |
| A11Y-01 | Manual WCAG 2.2 AA audit sign-off | High | In Progress | `ResearchHub Dev + Accessibility QA (to assign)` | `2026-03-17` | Keyboard + screen reader audit completed with no blocking issues | Manual audit notes + defect links |

## Daily Update Format

Use this section in daily release standup:

| Date | ID | Update | New Status | Owner | Next Action | ETA |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-03-05 | SEC-01 | Internal prep complete; awaiting vendor booking | In Progress | `ResearchHub Dev` | Finalize statement of work and test window | 2026-03-26 |

## Definition of Ready to Call "Global-Ready"

All conditions below must be true:
1. All blockers in this sheet are `Closed`.
2. `docs/release/global-launch-evidence-YYYY-MM-DD.md` is updated with linked artifacts.
3. Release sign-off document is completed and approved by Security, Platform/SRE, Legal, and Product.
