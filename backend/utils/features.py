"""
utils/features.py — Feature flag & access-control helpers.

Usage
-----
from utils.features import require_pro, is_admin, check_feature_flag

# In a route dependency or route body:
require_pro(current_user)           # raises 403 if user is not pro/admin
if is_admin(current_user):
    ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import HTTPException

if TYPE_CHECKING:
    from repositories.research import User


# ---------------------------------------------------------------------------
# Role helpers
# ---------------------------------------------------------------------------

def is_admin(user: "User") -> bool:
    """Return True if the user has administrator privileges."""
    return str(getattr(user, "role", "user") or "user").lower() == "admin"


def is_pro(user: "User") -> bool:
    """Return True if the user has pro or admin privileges."""
    role = str(getattr(user, "role", "user") or "user").lower()
    return bool(getattr(user, "is_pro", False)) or role in ("pro", "admin")


def require_pro(user: "User") -> None:
    """Raise HTTP 403 if the user does not have pro/admin privileges.

    Inject this at the top of any endpoint that requires a paid / advanced
    account, e.g.::

        @router.post("/ai/advanced")
        async def advanced_ai(current_user: User = Depends(get_current_user)):
            require_pro(current_user)
            ...
    """
    if not is_pro(user):
        raise HTTPException(
            status_code=403,
            detail="This feature requires a Pro account. Upgrade to unlock it.",
        )


def require_admin(user: "User") -> None:
    """Raise HTTP 403 if the user is not an administrator."""
    if not is_admin(user):
        raise HTTPException(
            status_code=403,
            detail="Administrator access required.",
        )


# ---------------------------------------------------------------------------
# Per-user feature flag override
# ---------------------------------------------------------------------------

def user_has_flag(user: "User", flag_name: str) -> bool:
    """Check a per-user feature flag override stored in Firestore.

    Feature flags are stored as a dict on the User document::

        {
          "feature_flags": {
            "advanced_search": true,
            "beta_export": false
          }
        }

    Falls back to False if the flag is absent.
    """
    flags: dict[str, Any] = getattr(user, "feature_flags", {}) or {}
    return bool(flags.get(flag_name, False))


def check_global_flag(flag_name: str, repo: Any) -> bool:
    """Check a global feature flag stored in the Firestore ``feature_flags`` collection.

    Documents in ``feature_flags/{flag_name}`` are expected to have::

        {
          "enabled": bool,
          "description": str,         # optional
          "rollout_pct": int,          # 0-100, optional
          "user_allowlist": [str]      # optional email allowlist
        }

    Returns True if the flag is enabled globally. For rollout_pct / allowlist
    logic, caller should use ``user_has_flag`` first.
    """
    try:
        db = getattr(repo, "db", None)
        if db is None:
            return False
        doc = db.collection("feature_flags").document(flag_name).get()
        if not doc.exists:
            return False
        data = doc.to_dict() or {}
        return bool(data.get("enabled", False))
    except Exception:
        return False
