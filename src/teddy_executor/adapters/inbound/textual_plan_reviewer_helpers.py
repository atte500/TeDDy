from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from teddy_executor.core.domain.models.plan import ActionData

MAX_LABEL_LENGTH = 60


def get_action_summary(action: "ActionData") -> str:
    """Extract a concise summary for the action."""
    summary = action.description or ""
    if not summary:
        params = action.params
        summary = str(
            params.get("path") or params.get("resource") or params.get("command", "")
        )

        if action.type == "PROMPT" and not summary:
            msg = str(params.get("prompt", "")).strip().split("\n")[0]
            summary = msg

    if len(summary) > MAX_LABEL_LENGTH:
        summary = summary[: MAX_LABEL_LENGTH - 3] + "..."
    return summary


def resolve_action_parameters(action: "ActionData") -> dict[str, Any]:
    """Resolves the full set of parameters for an action, including defaults."""
    from teddy_executor.core.domain.models.plan import (
        DEFAULT_SIMILARITY_THRESHOLD,
    )

    # Base defaults for all actions
    defaults: dict[str, Any] = {
        "overwrite": False,
        "match_all": False,
        "allow_failure": False,
        "background": False,
        "timeout": 30.0,
        "similarity_threshold": DEFAULT_SIMILARITY_THRESHOLD,
    }

    # Type-specific relevant parameters
    param_map = {
        "CREATE": ["path", "overwrite", "description"],
        "EDIT": ["path", "match_all", "similarity_threshold", "description"],
        "EXECUTE": [
            "command",
            "allow_failure",
            "background",
            "timeout",
            "description",
        ],
        "READ": ["resource", "description"],
        "PRUNE": ["resource", "description"],
        "RESEARCH": ["queries", "description"],
        "PROMPT": ["prompt"],
        "INVOKE": ["agent", "description"],
        "RETURN": ["description"],
    }

    keys = param_map.get(action.type, [])
    # Hide description from the detail view to reduce clutter
    keys = [k for k in keys if k != "description"]
    resolved = {}
    for key in keys:
        # Use provided value if exists, else fallback to default (if one exists for that key)
        if key in action.params:
            resolved[key] = action.params[key]
        elif key in defaults:
            resolved[key] = defaults[key]
        else:
            resolved[key] = None

    if action.type == "PROMPT":
        resolved["response"] = getattr(action, "user_response", None) or ""

    return resolved
