# OWASP Scan Operations

## Automated
- GitHub workflow: `.github/workflows/security-scans.yml`
- Manual dispatch input:
  - `target_url`: production/staging URL for baseline scan

## Local Run (Docker)
```powershell
docker run --rm -t owasp/zap2docker-stable zap-baseline.py -t https://app.example.com -a
```

## Triage Standard
1. `High`/`Critical`: patch before release.
2. `Medium`: patch in current sprint.
3. `Low`: backlog with owner/date.
4. False positives: document with evidence and expiry review date.

## Evidence Retention
- Keep raw scan output and issue triage notes for at least 12 months.
