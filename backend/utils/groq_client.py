import os
import logging
from threading import Lock
from typing import Any, Dict, List, Optional
from groq import Groq
from dotenv import load_dotenv
from pathlib import Path

# Load backend/.env first and allow it to override stale process values so local
# runs pick up current credentials.
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True)
load_dotenv(override=False)

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


MODEL_CONFIG: Dict[str, Any] = {
    "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    "temperature": _as_float("GROQ_TEMPERATURE", 0.2),
    "max_tokens": _as_int("GROQ_MAX_TOKENS", 2400),
    "top_p": _as_float("GROQ_TOP_P", 0.9),
}

# Profile for long-form synthesis workloads (mindmaps/reviews).
LONGFORM_MODEL_CONFIG: Dict[str, Any] = {
    "model": os.getenv("GROQ_LONGFORM_MODEL", MODEL_CONFIG["model"]),
    "temperature": _as_float("GROQ_LONGFORM_TEMPERATURE", 0.15),
    "max_tokens": _as_int("GROQ_LONGFORM_MAX_TOKENS", 3600),
    "top_p": _as_float("GROQ_LONGFORM_TOP_P", 0.9),
}

_DEFAULT_ALLOWED_MODELS: List[str] = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "deepseek-r1-distill-llama-70b",
]


def _parse_allowed_models() -> List[str]:
    raw = (os.getenv("GROQ_ALLOWED_MODELS") or "").strip()
    if not raw:
        models = list(_DEFAULT_ALLOWED_MODELS)
    else:
        models = [item.strip() for item in raw.split(",") if item.strip()]

    # Ensure configured defaults are always selectable.
    for candidate in (MODEL_CONFIG.get("model"), LONGFORM_MODEL_CONFIG.get("model")):
        if candidate and candidate not in models:
            models.append(str(candidate))
    return models


_ALLOWED_MODELS: List[str] = _parse_allowed_models()
_MODEL_LOCK = Lock()
_ACTIVE_MODEL = str(MODEL_CONFIG.get("model") or "llama-3.3-70b-versatile")
_ACTIVE_LONGFORM_MODEL = str(LONGFORM_MODEL_CONFIG.get("model") or _ACTIVE_MODEL)


def model_config(longform: bool = False, **overrides: Any) -> Dict[str, Any]:
    base = dict(LONGFORM_MODEL_CONFIG if longform else MODEL_CONFIG)
    base["model"] = _ACTIVE_LONGFORM_MODEL if longform else _ACTIVE_MODEL
    for key, value in overrides.items():
        if value is not None:
            base[key] = value
    return base


def groq_client_status() -> Dict[str, Any]:
    with _MODEL_LOCK:
        active_model = _ACTIVE_MODEL
        active_longform = _ACTIVE_LONGFORM_MODEL
    return {
        "configured": GROQ_CONFIGURED,
        "enabled": client is not None,
        "error": GROQ_CLIENT_ERROR,
        "available_models": list(_ALLOWED_MODELS),
        "active_model": active_model,
        "active_longform_model": active_longform,
    }


def set_active_models(model: str, longform_model: Optional[str] = None) -> Dict[str, Any]:
    default_model = (model or "").strip()
    if not default_model:
        raise ValueError("Model name is required.")

    long_model = (longform_model or default_model).strip()
    if not long_model:
        raise ValueError("Longform model name is invalid.")

    if _ALLOWED_MODELS and default_model not in _ALLOWED_MODELS:
        raise ValueError(f"Model '{default_model}' is not in allowed model list.")
    if _ALLOWED_MODELS and long_model not in _ALLOWED_MODELS:
        raise ValueError(f"Longform model '{long_model}' is not in allowed model list.")

    global _ACTIVE_MODEL, _ACTIVE_LONGFORM_MODEL
    with _MODEL_LOCK:
        _ACTIVE_MODEL = default_model
        _ACTIVE_LONGFORM_MODEL = long_model
        current = {
            "active_model": _ACTIVE_MODEL,
            "active_longform_model": _ACTIVE_LONGFORM_MODEL,
            "available_models": list(_ALLOWED_MODELS),
        }
    return current
