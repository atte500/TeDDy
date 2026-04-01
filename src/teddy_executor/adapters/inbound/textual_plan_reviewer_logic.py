import os
import pathlib
import anyio
from typing import TYPE_CHECKING, Any, Optional, cast

from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    ConfirmScreen,
    ParameterEditModal,
    PathInputScreen,
    StatusBar,
)

if TYPE_CHECKING:
    from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
    from teddy_executor.core.domain.models.plan import ActionData, Plan


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


async def preview_edit(app: "ReviewerApp", action: "ActionData", node: Any) -> None:
    """Handle preview for EDIT."""
    if not app._file_system:
        return
    path_str: str = action.params.get("path", "")
    suffix = pathlib.Path(path_str).suffix or ".txt"
    try:
        original = app._file_system.read_file(path_str)
    except Exception:
        original = ""
    proposed, _ = app._edit_simulator.simulate_edits(
        original, action.params.get("edits", [])
    )
    diff_viewer = app._console_tooling.get_diff_viewer_command()
    if diff_viewer:
        before = app._system_env.create_temp_file(suffix=f".before{suffix}")
        after = app._system_env.create_temp_file(suffix=f".after{suffix}")
        try:
            with open(before, "w", encoding="utf-8") as f:
                f.write(original)
            with open(after, "w", encoding="utf-8") as f:
                f.write(proposed)
            await anyio.to_thread.run_sync(
                app._system_env.run_command, diff_viewer + [before, after]
            )
            with open(after, "r", encoding="utf-8") as f:
                final = f.read()
        finally:
            app._system_env.delete_file(before)
            app._system_env.delete_file(after)
    else:
        final = await launch_editor(app, proposed, suffix=suffix)
    if final is not None and await app.push_screen_wait(ConfirmScreen()):
        if final != proposed:
            action.params["content"] = final
            action.modified = True
            app._refresh_node(node)


async def preview_create(app: "ReviewerApp", action: "ActionData", node: Any) -> None:
    """Handle preview for CREATE."""
    path_str = action.params.get("path", "")
    content = action.params.get("content", "")
    new_content = await launch_editor(
        app, content, suffix=pathlib.Path(path_str).suffix or ".txt"
    )
    if new_content is None:
        return
    new_path = await app.push_screen_wait(PathInputScreen(path_str))
    if new_path is not None and await app.push_screen_wait(ConfirmScreen()):
        action.params["content"] = new_content
        action.params["path"] = new_path
        action.modified = True
        app._refresh_node(node)


async def preview_text_action(
    app: "ReviewerApp", action: "ActionData", node: Any
) -> None:
    """Handle preview for EXECUTE/RESEARCH."""
    key = "command" if action.type == "EXECUTE" else "queries"
    content = action.params.get(key, "")
    new_content = await launch_editor(
        app, content, suffix=".sh" if action.type == "EXECUTE" else ".txt"
    )
    if new_content is not None and await app.push_screen_wait(ConfirmScreen()):
        if new_content.strip() != content.strip():
            action.params[key] = new_content.strip()
            action.modified = True
            app._refresh_node(node)


async def preview_readonly(app: "ReviewerApp", action: "ActionData") -> None:
    """Handle preview for READ/PRUNE."""
    if not app._file_system:
        return
    resource = action.params.get("resource") or action.params.get("path", "")
    try:
        content = app._file_system.read_file(resource)
    except Exception:
        content = f"--- Content for {resource} could not be retrieved ---"
    await launch_editor(app, content, suffix=pathlib.Path(resource).suffix or ".txt")


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
    elif action.type == "CREATE":
        await preview_create(app, action, node)
    elif action.type == "EDIT":
        await preview_edit(app, action, node)
    elif action.type in ("READ", "PRUNE"):
        await preview_readonly(app, action)


def toggle_all_logic(app: "ReviewerApp", plan: "Plan") -> None:
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
