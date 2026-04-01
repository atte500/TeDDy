from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any, Optional, cast

import anyio

from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    ParameterEditModal,
    StatusBar,
)

if TYPE_CHECKING:
    from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
    from teddy_executor.core.domain.models.plan import ActionData


async def launch_editor(
    app: "ReviewerApp", initial_content: str, suffix: str = ".txt"
) -> Optional[str]:
    """Suspends the TUI and launches an external editor."""
    mock_output = os.environ.get("TEDDY_TEST_MOCK_EDITOR_OUTPUT")
    if mock_output:
        return mock_output

    temp_file = app._system_env.create_temp_file(suffix=suffix)
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(initial_content)

        editor_cmd = app._console_tooling.find_editor()
        if not editor_cmd:
            return None

        editor_name = os.path.basename(editor_cmd[0])
        status_bar = cast(StatusBar, app.query_one("StatusBar"))
        status_bar.update_status(f"LAUNCHING: {editor_name} {temp_file}")

        editor_exe = editor_cmd[0].lower()
        is_gui = any(gui in editor_exe for gui in ["code", "zed", "subl", "cursor"])

        if is_gui:
            await anyio.to_thread.run_sync(
                app._system_env.run_command, editor_cmd + [temp_file]
            )
        else:
            with app.suspend():
                await anyio.to_thread.run_sync(
                    app._system_env.run_command, editor_cmd + [temp_file]
                )

        with open(temp_file, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None
    finally:
        app._system_env.delete_file(temp_file)


# Functions preview_edit, preview_create, preview_text_action, preview_readonly
def extract_status_emoji(raw_status: str) -> str:
    """Extracts the last emoji from a status string."""
    # A simple regex to find common status emojis.
    # This is not exhaustive but covers the expected cases.
    emojis = re.findall(r"[🟢🟡🔴]", raw_status)
    return emojis[-1] if emojis else ""


async def do_preview_logic(app: ReviewerApp, node: Any, action: ActionData) -> None:
    """Internal logic for previewing/modifying complex actions."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
        preview_create,
        preview_edit,
        preview_prompt,
        preview_readonly,
        preview_text_action,
    )

    if action.type == "CREATE":
        await preview_create(app, action, node)
    elif action.type == "EDIT":
        await preview_edit(app, action, node)
    elif action.type == "PROMPT":
        await preview_prompt(app, action, node)
    elif action.type in ("EXECUTE", "RESEARCH"):
        await preview_text_action(app, action, node)
    elif action.type in ("READ", "PRUNE"):
        await preview_readonly(app, action)


def format_node_label(action: "ActionData") -> str:
    """Format the label for a tree node based on action state."""
    summary = get_action_summary(action)
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
    params = action.params
    return params.get("path") or params.get("resource") or params.get("command", "")


async def edit_action_logic(
    app: "ReviewerApp", node: Any, action: "ActionData"
) -> None:
    """Handles the (e)dit key logic by branching to modals or external editor."""
    if action.type == "EXECUTE":
        val = action.params.get("command", "")
        new_val = await app.push_screen_wait(ParameterEditModal("Command:", val))
        if new_val is not None and new_val != val:
            action.params["command"] = new_val
            action.modified = True
            app._refresh_node(node)
    elif action.type == "RESEARCH":
        val = action.params.get("queries", "")
        new_val = await app.push_screen_wait(ParameterEditModal("Queries:", val))
        if new_val is not None and new_val != val:
            action.params["queries"] = new_val
            action.modified = True
            app._refresh_node(node)
    # Fallback to existing preview logic for complex types
    else:
        await do_preview_logic(app, node, action)


def refresh_node_logic(app: ReviewerApp, node: Any) -> None:
    """Refresh the label and state of a single tree node."""
    if node.data:
        node.label = format_node_label(node.data)


def on_mount_logic(app: Any) -> None:
    """Populate the action tree and set title when the app is mounted."""
    status_raw = app.plan.metadata.get("Status", "")
    status_emoji = extract_status_emoji(status_raw)
    title_parts = [part for part in [status_emoji, app.plan.title] if part]
    app.title = " ".join(title_parts)

    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
        ActionTree,
        ParameterList,
    )

    tree = app.query_one(ActionTree)
    param_tree = app.query_one(ParameterList)
    param_tree.show_root = False

    tree.root.expand()
    for action in app.plan.actions:
        if action.type == "PRUNE" and not app.plan.is_session:
            continue
        tree.root.add_leaf(format_node_label(action), data=action)
    tree.focus()


def check_action_logic(app: ReviewerApp, action_name: str) -> bool:
    """Gate for enabling/disabling bindings based on state."""
    if action_name == "revert":
        from textual.widgets import Tree

        tree = app.query_one(Tree)
        node = tree.cursor_node
        if not node:
            return False
        data: ActionData | None = node.data
        return bool(data and data.modified)
    return True


def toggle_selection_logic(app: ReviewerApp, node: Any) -> None:
    """Toggle action selection when a node is selected."""
    action: Optional["ActionData"] = node.data
    if action is not None and not action.executed:
        action.selected = not action.selected
        app._refresh_node(node)


def revert_logic(app: "ReviewerApp", node: Any) -> None:
    """Revert manual modifications for the currently highlighted action."""
    action: Optional["ActionData"] = node.data
    if action and action.modified:
        action.modified = False
        app._refresh_node(node)
        app.refresh_bindings()


def execute_step_logic(app: "ReviewerApp", node: Any) -> None:
    """Mark the currently highlighted action as executed and successful."""
    from teddy_executor.core.domain.models.plan import ExecutionStatus

    action: Optional["ActionData"] = node.data
    if action and not action.executed:
        action.executed = True
        action.state = ExecutionStatus.SUCCESS
        app._refresh_node(node)
        status_bar = cast(StatusBar, app.query_one("StatusBar"))
        status_bar.update_status(f"EXECUTED: {action.type}")


def toggle_all_logic(app: "ReviewerApp", plan: Any) -> None:
    """Toggle selection for all actions."""
    any_unselected = any(not action.selected for action in plan.actions)
    new_state = any_unselected

    for action in plan.actions:
        action.selected = new_state

    # Refresh all child nodes in the tree
    from textual.widgets import Tree

    tree = app.query_one(Tree)
    for node in tree.root.children:
        app._refresh_node(node)
