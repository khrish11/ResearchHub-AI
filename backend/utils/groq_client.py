import os
import logging
import inspect
from threading import Lock
from typing import Any, Dict, List, Optional
import httpx
from groq import Groq
from dotenv import load_dotenv
from pathlib import Path

# Load backend/.env without clobbering explicit process env. This keeps local
# credentials working while still allowing tests and deployment envs to set
# authoritative overrides such as STORAGE_BACKEND or DATABASE_URL.
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)
load_dotenv(override=False)


def _apply_httpx_proxy_compatibility_patch() -> None:
    """Allow SDKs still passing `proxies=` to run on httpx 0.28+."""
    if "proxies" in inspect.signature(httpx.Client.__init__).parameters:
        return

    def _translate_proxy_value(proxies: Any) -> Any:
        if isinstance(proxies, str):
            return proxies
        if isinstance(proxies, dict):
            for key in ("all://", "https://", "http://"):
                if proxies.get(key):
                    return proxies[key]
        return None

    original_client_init = httpx.Client.__init__
    original_async_client_init = httpx.AsyncClient.__init__

    def patched_client_init(self, *args: Any, proxies: Any = None, **kwargs: Any):
        translated = _translate_proxy_value(proxies)
        if translated and "proxy" not in kwargs:
            kwargs["proxy"] = translated
        return original_client_init(self, *args, **kwargs)

    def patched_async_client_init(self, *args: Any, proxies: Any = None, **kwargs: Any):
        translated = _translate_proxy_value(proxies)
        if translated and "proxy" not in kwargs:
            kwargs["proxy"] = translated
        return original_async_client_init(self, *args, **kwargs)

    httpx.Client.__init__ = patched_client_init  # type: ignore[assignment]
    httpx.AsyncClient.__init__ = patched_async_client_init  # type: ignore[assignment]


_apply_httpx_proxy_compatibility_patch()

api_key = (os.getenv("GROQ_API_KEY") or "").strip()
GROQ_CONFIGURED = bool(api_key)
GROQ_CLIENT_ERROR: Optional[str] = None

# Only create the Groq client when an API key is provided. Otherwise keep
# `client` as None so import-time failures are avoided and callers can
# handle unavailability at runtime.
if api_key:
    try:
        client = Groq(api_key=api_key)
    except Exception as exc:
        client = None
        err_text = str(exc)
        if "unexpected keyword argument 'proxies'" in err_text:
            GROQ_CLIENT_ERROR = (
                "Groq/httpx dependency mismatch. Run: pip install groq==0.4.1 httpx==0.25.2"
            )
        else:
            GROQ_CLIENT_ERROR = err_text
        logging.warning(
            "Groq client initialization failed (%s). "
            "AI calls will be disabled for this process.",
            exc,
        )
else:
    client = None
    GROQ_CLIENT_ERROR = "GROQ_API_KEY is missing."
    logging.warning(
        "GROQ_API_KEY not found in environment variables. "
        "AI calls will be disabled; set GROQ_API_KEY to enable them."
    )


def _as_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _as_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default

DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
DECOMMISSIONED_GROQ_MODELS = {"deepseek-r1-distill-llama-70b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"}


def _normalize_model_name(raw_value: Optional[str], fallback: str) -> str:
    candidate = str(raw_value or "").strip()
    if not candidate:
        return fallback
    if candidate in DECOMMISSIONED_GROQ_MODELS:
        logging.warning(
            "Configured Groq model '%s' is decommissioned. Falling back to '%s'.",
            candidate,
            fallback,
        )
        return fallback
    return candidate


MODEL_CONFIG: Dict[str, Any] = {
    "model": _normalize_model_name(os.getenv("GROQ_MODEL"), DEFAULT_GROQ_MODEL),
    "temperature": _as_float("GROQ_TEMPERATURE", 0.2),
    "max_tokens": _as_int("GROQ_MAX_TOKENS", 2400),
    "top_p": _as_float("GROQ_TOP_P", 0.9),
}

# Profile for long-form synthesis workloads (mindmaps/reviews).
LONGFORM_MODEL_CONFIG: Dict[str, Any] = {
    "model": _normalize_model_name(
        os.getenv("GROQ_LONGFORM_MODEL"), str(MODEL_CONFIG["model"])
    ),
    "temperature": _as_float("GROQ_LONGFORM_TEMPERATURE", 0.15),
    "max_tokens": _as_int("GROQ_LONGFORM_MAX_TOKENS", 3600),
    "top_p": _as_float("GROQ_LONGFORM_TOP_P", 0.9),
}

TASK_MODEL_LABELS: Dict[str, str] = {
    "chat": "Chat",
    "upload_summary": "Upload Summary",
    "mindmap": "Mindmap / Report",
    "pipeline": "Pipeline / Agent",
}

TASK_MODEL_ENV_MAP: Dict[str, str] = {
    "chat": "GROQ_CHAT_MODEL",
    "upload_summary": "GROQ_UPLOAD_SUMMARY_MODEL",
    "mindmap": "GROQ_MINDMAP_MODEL",
    "pipeline": "GROQ_PIPELINE_MODEL",
}

LONGFORM_TASKS = {"mindmap", "pipeline"}

_DEFAULT_ALLOWED_MODELS: List[str] = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-safeguard-20b",
    "groq/compound",
    "groq/compound-mini",
    "qwen/qwen3.6-27b",
]


def _parse_allowed_models() -> List[str]:
    raw = (os.getenv("GROQ_ALLOWED_MODELS") or "").strip()
    if not raw:
        models = list(_DEFAULT_ALLOWED_MODELS)
    else:
        models = [item.strip() for item in raw.split(",") if item.strip()]
    models = [model for model in models if model not in DECOMMISSIONED_GROQ_MODELS]

    # Ensure configured defaults are always selectable.
    for candidate in (MODEL_CONFIG.get("model"), LONGFORM_MODEL_CONFIG.get("model")):
        if candidate and candidate not in models:
            models.append(str(candidate))
    for env_name in TASK_MODEL_ENV_MAP.values():
        candidate = _normalize_model_name(os.getenv(env_name), "")
        if candidate and candidate not in models:
            models.append(candidate)
    return models


def _normalize_task(task: Optional[str]) -> Optional[str]:
    candidate = str(task or "").strip().lower()
    return candidate if candidate in TASK_MODEL_ENV_MAP else None


def _default_task_model(task: str) -> str:
    if task in LONGFORM_TASKS:
        return str(
            LONGFORM_MODEL_CONFIG.get("model")
            or MODEL_CONFIG.get("model")
            or DEFAULT_GROQ_MODEL
        )
    return str(MODEL_CONFIG.get("model") or DEFAULT_GROQ_MODEL)


def _parse_task_models() -> Dict[str, str]:
    task_models: Dict[str, str] = {}
    for task, env_name in TASK_MODEL_ENV_MAP.items():
        value = _normalize_model_name(os.getenv(env_name), _default_task_model(task))
        task_models[task] = value
    return task_models


_ALLOWED_MODELS: List[str] = _parse_allowed_models()
_MODEL_LOCK = Lock()
_ACTIVE_MODEL = str(MODEL_CONFIG.get("model") or DEFAULT_GROQ_MODEL)
_ACTIVE_LONGFORM_MODEL = str(LONGFORM_MODEL_CONFIG.get("model") or _ACTIVE_MODEL)
_ACTIVE_TASK_MODELS: Dict[str, str] = _parse_task_models()

def model_config(longform: bool = False, task: Optional[str] = None, **overrides: Any) -> Dict[str, Any]:
    canonical_task = _normalize_task(task)
    use_longform = bool(longform or (canonical_task in LONGFORM_TASKS))
    base = dict(LONGFORM_MODEL_CONFIG if use_longform else MODEL_CONFIG)
    if canonical_task:
        base["model"] = _ACTIVE_TASK_MODELS.get(canonical_task) or (
            _ACTIVE_LONGFORM_MODEL if use_longform else _ACTIVE_MODEL
        )
    else:
        base["model"] = _ACTIVE_LONGFORM_MODEL if use_longform else _ACTIVE_MODEL
    for key, value in overrides.items():
        if value is not None:
            base[key] = value
    return base


def groq_client_status() -> Dict[str, Any]:
    with _MODEL_LOCK:
        active_model = _ACTIVE_MODEL
        active_longform = _ACTIVE_LONGFORM_MODEL
        active_task_models = dict(_ACTIVE_TASK_MODELS)
    return {
        "configured": GROQ_CONFIGURED,
        "enabled": client is not None,
        "error": GROQ_CLIENT_ERROR,
        "available_models": list(_ALLOWED_MODELS),
        "active_model": active_model,
        "active_longform_model": active_longform,
        "active_task_models": active_task_models,
        "task_model_labels": dict(TASK_MODEL_LABELS),
    }


def set_active_models(
    model: str,
    longform_model: Optional[str] = None,
    task_models: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    default_model = (model or "").strip()
    if not default_model:
        raise ValueError("Model name is required.")

    long_model = (longform_model or default_model).strip()
    if not long_model:
        raise ValueError("Longform model name is invalid.")
    if default_model in DECOMMISSIONED_GROQ_MODELS:
        raise ValueError(
            f"Model '{default_model}' has been decommissioned by Groq. Use '{DEFAULT_GROQ_MODEL}'."
        )
    if long_model in DECOMMISSIONED_GROQ_MODELS:
        raise ValueError(
            f"Longform model '{long_model}' has been decommissioned by Groq. Use '{DEFAULT_GROQ_MODEL}'."
        )

    if _ALLOWED_MODELS and default_model not in _ALLOWED_MODELS:
        raise ValueError(f"Model '{default_model}' is not in allowed model list.")
    if _ALLOWED_MODELS and long_model not in _ALLOWED_MODELS:
        raise ValueError(f"Longform model '{long_model}' is not in allowed model list.")

    normalized_task_models: Dict[str, str] = {}
    for task_name, raw_value in (task_models or {}).items():
        canonical_task = _normalize_task(task_name)
        if not canonical_task:
            raise ValueError(f"Unsupported task model slot '{task_name}'.")
        task_model = str(raw_value or "").strip()
        if not task_model:
            raise ValueError(f"Task model for '{task_name}' is invalid.")
        if task_model in DECOMMISSIONED_GROQ_MODELS:
            raise ValueError(
                f"Task model '{task_model}' has been decommissioned by Groq. Use '{DEFAULT_GROQ_MODEL}'."
            )
        if _ALLOWED_MODELS and task_model not in _ALLOWED_MODELS:
            raise ValueError(f"Task model '{task_model}' is not in allowed model list.")
        normalized_task_models[canonical_task] = task_model

    global _ACTIVE_MODEL, _ACTIVE_LONGFORM_MODEL
    with _MODEL_LOCK:
        _ACTIVE_MODEL = default_model
        _ACTIVE_LONGFORM_MODEL = long_model
        if normalized_task_models:
            _ACTIVE_TASK_MODELS.update(normalized_task_models)
        current = {
            "active_model": _ACTIVE_MODEL,
            "active_longform_model": _ACTIVE_LONGFORM_MODEL,
            "active_task_models": dict(_ACTIVE_TASK_MODELS),
            "task_model_labels": dict(TASK_MODEL_LABELS),
            "available_models": list(_ALLOWED_MODELS),
        }
    return current
