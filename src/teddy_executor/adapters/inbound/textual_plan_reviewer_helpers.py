from __future__ import annotations
import logging
import os
import re
from typing import TYPE_CHECKING, Any, Optional, cast

if TYPE_CHECKING:
    from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
    from teddy_executor.core.domain.models.plan import ActionData

logger = logging.getLogger(__name__)

MAX_LABEL_LENGTH = 60


def extract_status_emoji(raw_status: str) -> str:
    """Extracts the last emoji from a status string."""
    emojis = re.findall(r"[🟢🟡🔴]", raw_status)
    return emojis[-1] if emojis else ""


# Editor helpers moved to textual_plan_reviewer_editor.py


def format_node_label(action: "ActionData") -> str:
    """Format the label for a tree node based on action state."""
    from teddy_executor.core.domain.models.plan import ExecutionStatus

    summary = get_action_summary(action)
    # Ensure Enum types are stringified (e.g. ActionType.CREATE -> "CREATE")
    type_str = action.type.value if hasattr(action.type, "value") else str(action.type)

    if action.state == ExecutionStatus.RUNNING:
        return f"[blue][RUNNING] {type_str}: {summary}[/]"

    if action.executed:
        color = "green" if action.state.value == "SUCCESS" else "red"
        return f"[{color}][{action.state.value}] {type_str}: {summary}[/]"

    prefix = "[✓]" if action.selected else "[ ]"
    label = f"{prefix} {type_str}: {summary}"
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


def _apply_param_edit(action: Any, key: str, _old_val: Any, new_val: str) -> None:
    """Helper to apply parameter edits back to the action."""
    if action.type == "PROMPT" and key == "response":
        action.user_response = str(new_val)
        return

    # Check if the parameter should be a list based on action type/key
    list_keys = {"queries", "reference_files"}
    if key in list_keys:
        action.params[key] = [v.strip() for v in str(new_val).split(",") if v.strip()]
    else:
        action.params[key] = str(new_val)


async def handle_list_view_selected(
    app: "ReviewerApp", item: Any, update_fn: Any
) -> None:
    """Handle parameter editing when a DetailItem is selected in the right pane."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
        ActionTree,
        PathInputScreen,
        ParameterEditModal,
    )

    node = app.query_one(ActionTree).cursor_node
    if not node or not node.data or not hasattr(item, "data"):
        return

    action, key, val = node.data, item.data.get("key"), item.data.get("val")
    from teddy_executor.core.domain.models.plan import ActionData

    if not isinstance(action, ActionData) or action.executed:
        return

    if action.type == "PROMPT" and key == "prompt":
        return

    if key == "path":
        new_val = await cast(Any, app.push_screen_wait(PathInputScreen(str(val))))
    else:
        if not isinstance(val, (str, int, float, bool, list)) and val is not None:
            return
        v_str = ", ".join(map(str, val)) if isinstance(val, list) else str(val)
        new_val = await cast(
            Any, app.push_screen_wait(ParameterEditModal(f"{key}:", v_str))
        )

    if new_val is not None and str(new_val) != str(val):
        _apply_param_edit(action, key, val, new_val)
        action.modified = True
        if key and key not in action.modified_fields:
            action.modified_fields.append(key)
        app._refresh_node(node)
        update_fn(app, action)


async def handle_edit_action(
    app: ReviewerApp, node: Any, action: Any, update_fn: Any
) -> None:
    """Handles the (e)dit key logic by branching to modals or external editor."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
        ParameterEditModal,
    )
    from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
        do_preview_logic,
    )

    if action.type == "EXECUTE":
        val = action.params.get("command", "")
        new_val = await cast(
            Any, app.push_screen_wait(ParameterEditModal("Command:", val))
        )
        if new_val is not None and new_val != val:
            action.params["command"] = new_val
            action.modified = True
            if "command" not in action.modified_fields:
                action.modified_fields.append("command")
            app._refresh_node(node)
            update_fn(app, action)
    elif action.type == "RESEARCH":
        val = action.params.get("queries", [])
        val_str = ", ".join(val) if isinstance(val, list) else str(val)
        new_val = await cast(
            Any,
            app.push_screen_wait(
                ParameterEditModal("Queries (comma separated):", val_str)
            ),
        )
        if new_val is not None and new_val != val_str:
            action.params["queries"] = [
                q.strip() for q in new_val.split(",") if q.strip()
            ]
            action.modified = True
            if "queries" not in action.modified_fields:
                action.modified_fields.append("queries")
            app._refresh_node(node)
            update_fn(app, action)
    else:
        await do_preview_logic(app, node, action)
        update_fn(app, action)


def handle_revert(app: ReviewerApp, node: Any, update_fn: Any) -> None:
    """Revert manual modifications for the currently highlighted action."""
    action: Optional[ActionData] = node.data
    if action and action.modified:
        action.modified = False
        action.modified_fields.clear()
        if hasattr(action, "_original_params"):
            action.params = action._original_params.copy()
        if action.type == "PROMPT":
            action.user_response = None

        ptf = getattr(action, "pending_temp_file", None)
        if isinstance(ptf, str):
            app._system_env.delete_file(ptf)
        action.pending_temp_file = None

        app._refresh_node(node)
        update_fn(app, action)
        app.refresh_bindings()


def handle_jump_next(app: Any) -> None:
    """Logic for jumping to the next major section in the tree."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
        ActionTree,
    )

    tree = app.query_one(ActionTree)
    node = tree.cursor_node
    if not node:
        tree.jump_to_section(ActionTree.CONTEXT_ROOT)
    elif node.data == ActionTree.CONTEXT_ROOT:
        tree.jump_to_section(ActionTree.RATIONALE_ROOT)
    elif node.data == ActionTree.RATIONALE_ROOT:
        tree.jump_to_section(ActionTree.ACTION_PLAN_ROOT)
    else:
        tree.jump_to_section(ActionTree.CONTEXT_ROOT)
    tree.focus()


def handle_jump_prev(app: Any) -> None:
    """Logic for jumping to the previous major section in the tree."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
        ActionTree,
    )

    tree = app.query_one(ActionTree)
    node = tree.cursor_node
    if not node:
        tree.jump_to_section(ActionTree.ACTION_PLAN_ROOT)
    elif node.data == ActionTree.ACTION_PLAN_ROOT:
        tree.jump_to_section(ActionTree.RATIONALE_ROOT)
    elif node.data == ActionTree.RATIONALE_ROOT:
        tree.jump_to_section(ActionTree.CONTEXT_ROOT)
    else:
        tree.jump_to_section(ActionTree.ACTION_PLAN_ROOT)
    tree.focus()


def handle_submit(app: Any) -> None:
    """Logic for submitting the plan and closing the app."""

    # Harvest deferred changes from pending_temp_files
    for action in app.plan.actions:
        harvest_action_content(action, app.INSTRUCTION_MARKER)

    if app._user_message_cache is not None:
        marker = app.INSTRUCTION_MARKER.strip()
        if marker in app._user_message_cache:
            final_message: str = app._user_message_cache.split(marker)[0].strip()
        else:
            final_message = app._user_message_cache.strip()
        app.plan.metadata["user_request"] = final_message

    for f in getattr(app, "_log_preview_files", []):
        try:
            app._system_env.delete_file(f)
        except Exception:
            pass  # Silent failure is safe for transient cleanup

    app.exit(app.plan)


def handle_cancel(app: Any) -> None:
    """Logic for canceling the review and closing the app."""
    import os

    # Harvest message even on cancel so it can be propagated to the abort report
    if app._user_message_cache is not None:
        marker = app.INSTRUCTION_MARKER.strip()
        if marker in app._user_message_cache:
            final_message: str = app._user_message_cache.split(marker)[0].strip()
        else:
            final_message = app._user_message_cache.strip()
        app.plan.metadata["user_request"] = final_message

    # Cleanup any pending temp files
    for action in app.plan.actions:
        # Type guard for Mocks in tests
        is_valid_path = isinstance(action.pending_temp_file, (str, os.PathLike))
        if (
            action.pending_temp_file
            and is_valid_path
            and os.path.exists(action.pending_temp_file)
        ):
            try:
                os.remove(action.pending_temp_file)
                action.pending_temp_file = None
            except Exception:
                pass  # Silent failure is safe for transient cleanup

    for f in getattr(app, "_log_preview_files", []):
        try:
            app._system_env.delete_file(f)
        except Exception:
            pass  # Silent failure is safe for transient cleanup

    app.exit(None)


def harvest_action_content(action: Any, instruction_marker: str) -> None:
    """Harvest modified content from a pending temporary file back to the action."""
    # Type guard for Mocks in tests
    is_valid_path = isinstance(action.pending_temp_file, (str, os.PathLike))
    if not (
        action.pending_temp_file
        and is_valid_path
        and os.path.exists(action.pending_temp_file)
    ):
        return

    try:
        with open(action.pending_temp_file, "r", encoding="utf-8") as f:
            new_content = f.read()

        mapping = {"CREATE": "content", "EXECUTE": "command", "RESEARCH": "queries"}
        if action.type in mapping:
            action.params[mapping[action.type]] = new_content
        elif action.type == "PROMPT":
            marker = instruction_marker.strip()
            if marker in new_content:
                action.user_response = new_content.split(marker)[0].strip()
            else:
                action.user_response = new_content.strip()

        os.remove(action.pending_temp_file)
        action.pending_temp_file = None
    except Exception as e:
        logger.debug(
            "Failed to harvest action content from %s: %s", action.pending_temp_file, e
        )
