# -----------------------------------------------------------------------------
# Soyog AI - Production Monitoring & Alerting Guide
# -----------------------------------------------------------------------------

## 1. Monitoring Setup Steps

### Sentry Integration
Sentry has been integrated into `backend/main.py`. 
To activate it, simply add the DSN to your `.env` or cloud provider secrets:
```env
SENTRY_DSN=https://your-sentry-dsn-key@o0.ingest.sentry.io/0
```
This automatically captures:
- Unhandled Exception Stack Traces
- API Latency Profiles
- 500 Internal Server Errors

### Health Probes
The `/health/live` and `/health/ready` endpoints have been added via `routers/health.py`.
Configure your Cloud Load Balancer or Kubernetes deployment to ping them:
- **Liveness probe**: `GET /health/live` (Checks if the container is running).
- **Readiness probe**: `GET /health/ready` (Verifies connection latency to backend dependencies).

## 2. Alert Rules
Configure the following Alerting rules in Sentry or Google Cloud Monitoring to trigger notifications to your team.

| Metric / Condition | Threshold | Severity | Recommended Action |
| --- | --- | --- | --- |
| **Error Rate** | > 10% (5m window) | CRITICAL | Investigate database connections, Groq API outages, or bad rollouts. |
| **P95 Latency** | > 3000 ms (5m) | WARNING | Check Groq LLM latency; spin up more Uvicorn workers if CPU bound. |
| **Cache Hit Rate** | < 20% | INFO | Cache eviction may be too aggressive; adjust TTL in `cache_service.py`. |
| **AI Usage Spikes** | > 200% over baseline | WARNING | Monitor potentially anomalous token generation or heavy user scrapers. |

## 3. Integration Examples

### Slack Webhook Integration (Example)
Create a Slack incoming webhook and configure your monitoring provider (e.g. Sentry/GCP) to push JSON payloads to it.
```bash
curl -X POST -H 'Content-type: application/json' \
--data '{"text":"🚨 CRITICAL: Soyog AI Error Rate exceeded 10% in the last 5 minutes."}' \
YOUR_SLACK_WEBHOOK_URL
```

## 4. Logging Improvements
Logs have been structured natively using Google Cloud Logging JSON formats. The `request_logging_middleware` in `main.py` now includes:
- `event: "http_request"`
- `user_id`: Authenticated user UID (or `anonymous`) via route dependencies.
- `route`: The FastAPI URL path.
- `duration_ms`: Execution time tracking in milliseconds.
- `status_code`: Natively parsed status returns.
- `logging.googleapis.com/trace`: Automatic GCP distributed tracing identifier.

## 5. Cost Monitoring
Groq LLM inference cost can explode if unchecked.
- **Top Users Tracker**: The `/analytics/users` endpoint tracks the heaviest consumers of LLM endpoints. 
- **Token Usage Logs**: The `ai.py` router automatically injects token limits directly from Groq's usage responses into Firestore.
- **Rule of Thumb**: Audit the `ai_usage` Firestore collection weekly to find outliers.

## 6. Production Checklist
- [x] Integrate `sentry-sdk` into `main.py` and `requirements.txt`.
- [x] Configure Health routes (`/health/live`, `/health/ready`).
- [x] Enhance middleware to log user, route, duration, and status.
- [ ] Set `SENTRY_DSN` variable in production payload.
- [ ] Connect Sentry Alert Routing to the engineering Slack channel.
- [ ] Confirm Log Explorer queries in GCP properly filter `jsonPayload.duration_ms`.
