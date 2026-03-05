# Penetration Testing Playbook

## Scope
- Web app routes (public + authenticated)
- API endpoints (`/auth`, `/papers`, `/workspaces`, `/research-agent`, `/compliance`)
- Authentication/session handling
- File upload and export surfaces

## Methodology
1. Recon and attack-surface mapping
2. OWASP Top 10 test execution
3. Authz/authn abuse tests
4. Business-logic abuse scenarios
5. Data exfiltration and privilege escalation attempts
6. Reporting and retest

## Minimum Tooling
- OWASP ZAP baseline + active scan
- Burp Suite (manual)
- Nuclei templates (curated)
- API fuzzing (e.g. ffuf/kiterunner)

## Test Cases (Minimum)
1. Broken access control across user workspaces
2. JWT tampering / expired-token handling
3. Injection checks across query-heavy endpoints
4. SSRF/file handling checks on import/upload flows
5. Rate-limit bypass and brute-force checks on `/auth/*`
6. Sensitive data exposure in logs and responses
7. Dependency and secret leakage checks

## Deliverables
- Executive summary
- Technical findings with severity + CVSS + PoC
- Reproduction steps
- Remediation recommendations
- Verified retest report

## Cadence
- Full external penetration test: quarterly
- High-risk feature pen test: before production release
- Retest: within 14 days for critical/high findings
