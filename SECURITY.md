# Security Policy

## Supported Versions

Only the latest commit on `main`/`master` is supported for security fixes.

## Reporting a Vulnerability

1. Do not open a public issue for sensitive vulnerabilities.
2. Report privately to the project maintainer with:
   - affected endpoint/component
   - reproduction steps
   - expected vs actual behavior
   - impact assessment
3. Include whether authentication is required and whether exploit is remote.

## Response Targets

1. Initial acknowledgement: within 72 hours.
2. Triage classification (critical/high/medium/low): within 7 days.
3. Critical/high fix or mitigation: target within 14 days.
4. Public disclosure: after fix is available and users can upgrade.

## Secrets and Token Hygiene

1. Never commit secrets, API keys, PATs, or session tokens.
2. Use GitHub Actions secrets for CI (`Settings -> Secrets and variables -> Actions`).
3. Rotate exposed keys immediately and invalidate compromised credentials.
4. Review Windows Credential Manager or local credential stores after rotation.

## Security Testing Baseline

1. SAST + dependency scans: `.github/workflows/security-scans.yml`
2. Secret scanning: `.github/workflows/secret-scan.yml`
3. Penetration testing playbook: `docs/security/penetration-testing-playbook.md`
4. OWASP operations guide: `docs/security/owasp-scan-operations.md`
