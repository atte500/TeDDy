from __future__ import annotations
import os
import re
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from teddy_executor.core.domain.models.plan import ActionData

MAX_LABEL_LENGTH = 60


def extract_status_emoji(raw_status: str) -> str:
    """Extracts the last emoji from a status string."""
    emojis = re.findall(r"[🟢🟡🔴]", raw_status)
    return emojis[-1] if emojis else ""


def handle_mock_editor(path: Any, output: str) -> str:
    """Helper for mock editor output in tests."""
    if path and isinstance(path, (str, os.PathLike)):
        with open(path, "w", encoding="utf-8") as f:
            f.write(output)
    return output


def spawn_editor(cmd: list[str], path: Any) -> None:
    """Spawns an external editor process."""
    import subprocess  # nosec B404

    try:
        subprocess.Popen(cmd + [str(path)])  # nosec B603
    except Exception:  # nosec B110
        pass


def handle_mock_diff(p_file: Any, before: str, delete_fn: Any) -> bool:
    """Helper for mock diff output in tests."""
    mock_out = os.environ.get("TEDDY_TEST_MOCK_EDITOR_OUTPUT")
    if mock_out:
        with open(p_file, "w", encoding="utf-8") as f:
            f.write(mock_out)
        delete_fn(before)
        return True
    return False


def prepare_after_file(path: Any, proposed: str) -> None:
    """Ensures the 'after' file is ready for diffing/editing."""
    if os.path.exists(path):
        os.chmod(path, 0o644)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(proposed))


def harvest_edit_diff(action: Any, p_file: Any, original: str, proposed: str) -> None:
    """Helper to harvest diff results and update action params."""
    try:
        with open(p_file, "r", encoding="utf-8") as f:
            final: Optional[str] = f.read()
    except Exception:
        final = None
    if final is not None and str(final) != str(proposed):
        action.params["edits"] = [{"find": original, "replace": str(final)}]
        action.params.pop("content", None)


def format_node_label(action: "ActionData") -> str:
    """Format the label for a tree node based on action state."""
    from teddy_executor.core.domain.models.plan import ExecutionStatus

    summary = get_action_summary(action)
    if action.state == ExecutionStatus.RUNNING:
        return f"[blue][RUNNING] {action.type}: {summary}[/]"

    if action.executed:
        color = "green" if action.state.value == "SUCCESS" else "red"
        return f"[{color}][{action.state.value}] {action.type}: {summary}[/]"

    prefix = "[✓]" if action.selected else "[ ]"
    label = f"{prefix} {action.type}: {summary}"
    if action.modified:
        label += " *modified"
    return label


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

    # Include execution results if available
    if action.executed and action.action_log:
        log = action.action_log
        resolved["status"] = log.status.value
        if log.details:
            resolved["details"] = log.details
        if log.failed_command:
            resolved["failed_command"] = log.failed_command

    return resolved
