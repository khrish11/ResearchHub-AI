import os
import logging
from typing import Any, Dict
from groq import Groq
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)
load_dotenv(override=False)

api_key = (os.getenv("GROQ_API_KEY") or "").strip()

# Only create the Groq client when an API key is provided. Otherwise keep
# `client` as None so import-time failures are avoided and callers can
# handle unavailability at runtime.
if api_key:
    client = Groq(api_key=api_key)
else:
    client = None
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


def model_config(longform: bool = False, **overrides: Any) -> Dict[str, Any]:
    base = dict(LONGFORM_MODEL_CONFIG if longform else MODEL_CONFIG)
    for key, value in overrides.items():
        if value is not None:
            base[key] = value
    return base
