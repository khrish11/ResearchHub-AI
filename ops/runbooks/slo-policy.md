# SLO Policy

## Objectives
- Availability SLO: `99.9%` monthly for API requests.
- Latency SLO: `p95 < 500ms` for non-streaming endpoints.
- Error budget: `0.1%` monthly.

## Measurement
- Prometheus scrape: `/ops/metrics`
- SLO endpoint: `/ops/slo`
- Alerts:
  - 5xx rate above 1% for 10 minutes.
  - Rate-limit spikes above baseline for 5 minutes.

## Error Budget Rules
1. If budget burn > 50% in first half of month, freeze non-critical releases.
2. If budget burn > 80%, only reliability/security changes are allowed.
3. Resume feature rollout once burn rate stabilizes under target for 7 days.
