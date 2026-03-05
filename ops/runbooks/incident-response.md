# Incident Response Runbook

## Severity Levels
- `SEV-1`: Full outage, security breach, or data loss in progress.
- `SEV-2`: Major feature failure or sustained elevated error rates.
- `SEV-3`: Partial degradation with workarounds.

## First 10 Minutes
1. Acknowledge alert and open incident channel.
2. Assign incident commander and communications owner.
3. Check `/health/live`, `/health/ready`, `/ops/slo`.
4. Validate edge health (Cloudflare status, origin availability, TLS cert validity).
5. Decide on rollback, scale-up, or traffic-shed action.

## Core Checks
1. API error rate: `researchhub_http_status_total{status=~"5.."}`
2. Rate-limiting spikes: `researchhub_http_rate_limited_total`
3. Backend process restarts, memory, CPU saturation.
4. Database availability, lock contention, and file-system health.
5. Upstream provider outages (OpenAlex, ArXiv, Springer, etc.).

## Recovery Actions
1. Roll back to previous stable release.
2. Enable degraded mode (disable optional integrations).
3. Increase rate limits only after abuse checks.
4. Rotate credentials if compromise suspected.

## Post-Incident
1. Publish timeline, root cause, and impact.
2. Capture action items with owners and due dates.
3. Add regression tests and alert improvements.
