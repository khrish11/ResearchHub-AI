from __future__ import annotations

from typing import Any


def validate_runtime_configuration(
    *,
    app_env: str,
    rate_limit_enabled: bool,
    rate_limit_store: str,
    redis_url: str,
    enforce_distributed_rate_limit: bool,
    firebase_appcheck_enforced: bool,
    metrics_auth_token: str,
    logger: Any,
) -> None:
    is_production = str(app_env or "").strip().lower() == "production"
    if not is_production:
        return

    issues: list[str] = []
    warnings: list[str] = []

    normalized_store = str(rate_limit_store or "").strip().lower()
    if rate_limit_enabled and normalized_store != "redis":
        if enforce_distributed_rate_limit:
            issues.append(
                "RATE_LIMIT_STORE must be 'redis' in production when RATE_LIMIT_ENABLED=1 and ENFORCE_DISTRIBUTED_RATE_LIMIT=1."
            )
        else:
            warnings.append(
                "RATE_LIMIT_STORE is not 'redis' in production. Requests are rate-limited per-instance only. "
                "Set ENFORCE_DISTRIBUTED_RATE_LIMIT=1 to require Redis-backed global rate limits."
            )
    if normalized_store == "redis" and not str(redis_url or "").strip():
        issues.append("REDIS_URL is required when RATE_LIMIT_STORE=redis.")

    if not firebase_appcheck_enforced:
        warnings.append(
            "FIREBASE_APPCHECK_ENFORCED is disabled in production; enable it to reduce abuse risk."
        )
    if not str(metrics_auth_token or "").strip():
        warnings.append(
            "METRICS_AUTH_TOKEN is not set in production; /ops endpoints are not protected by shared token auth."
        )

    for warning in warnings:
        logger.warning(warning)

    if issues:
        raise RuntimeError("Invalid production runtime configuration: " + " ".join(issues))
