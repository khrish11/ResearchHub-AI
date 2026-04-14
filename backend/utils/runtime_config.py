from __future__ import annotations

from typing import Any


def validate_runtime_configuration(
    *,
    app_env: str,
    rate_limit_enabled: bool,
    rate_limit_store: str,
    redis_url: str,
    firebase_appcheck_enforced: bool,
    metrics_auth_token: str,
    logger: Any,
) -> None:
    is_production = str(app_env or "").strip().lower() == "production"
    if not is_production:
        return

    issues: list[str] = []
    warnings: list[str] = []

    if rate_limit_enabled and str(rate_limit_store or "").strip().lower() != "redis":
        issues.append(
            "RATE_LIMIT_STORE must be 'redis' in production when RATE_LIMIT_ENABLED=1."
        )
    if str(rate_limit_store or "").strip().lower() == "redis" and not str(redis_url or "").strip():
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
