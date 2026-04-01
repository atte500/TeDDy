from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
    from teddy_executor.core.domain.models.plan import ActionData
    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
        ConfirmScreen,
    )

from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    ConfirmScreen,
    PathInputScreen,
)


async def preview_edit(app: ReviewerApp, action: ActionData, node: Any) -> None:
    """Handle preview for EDIT."""
    import asyncio

    from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
        launch_editor,
    )

    if not app._file_system:
        return
    path_str = cast(str, action.params.get("path", ""))
    suffix = pathlib.Path(path_str).suffix or ".txt"
    try:
        original = app._file_system.read_file(path_str)
    except Exception:
        original = ""
    proposed, _ = app._edit_simulator.simulate_edits(
        original, action.params.get("edits", [])
    )
    diff_viewer = app._console_tooling.get_diff_viewer_command()

    async def _run_diff_viewer() -> str | None:
        if not diff_viewer:
            return None
        before = app._system_env.create_temp_file(suffix=f".before{suffix}")
        after = app._system_env.create_temp_file(suffix=f".after{suffix}")
        try:
            with open(before, "w", encoding="utf-8") as f:
                f.write(original)
            with open(after, "w", encoding="utf-8") as f:
                f.write(proposed)
            import anyio

            await anyio.to_thread.run_sync(
                app._system_env.run_command, diff_viewer + [before, after]
            )
            with open(after, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None
        finally:
            app._system_env.delete_file(before)
            app._system_env.delete_file(after)

    # Launch tool and confirmation concurrently
    if diff_viewer:
        tool_task = _run_diff_viewer()
    else:
        tool_task = launch_editor(app, proposed, suffix=suffix)

    confirm_task = app.push_screen_wait(ConfirmScreen())

    final, confirmed = await asyncio.gather(tool_task, confirm_task)

    if final is not None and confirmed:
        if final != proposed:
            action.params["content"] = final
            action.modified = True
            app._refresh_node(node)


async def preview_create(app: ReviewerApp, action: ActionData, node: Any) -> None:
    """Handle preview for CREATE."""
    import asyncio
    from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
        launch_editor,
    )

    path_str = cast(str, action.params.get("path", ""))
    content = cast(str, action.params.get("content", ""))

    # Launch editor and path input concurrently
    editor_task = launch_editor(
        app, content, suffix=pathlib.Path(path_str).suffix or ".txt"
    )
    path_task = app.push_screen_wait(cast(Any, PathInputScreen(path_str)))

    new_content, new_path_val = await asyncio.gather(editor_task, path_task)

    if new_content is not None and new_path_val is not None:
        if await app.push_screen_wait(ConfirmScreen()):
            action.params["content"] = cast(str, new_content)
            action.params["path"] = cast(str, new_path_val)
            action.modified = True
            app._refresh_node(node)


async def preview_text_action(app: ReviewerApp, action: ActionData, node: Any) -> None:
    """Handle preview for EXECUTE/RESEARCH."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
        launch_editor,
    )

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


async def preview_readonly(app: ReviewerApp, action: ActionData) -> None:
    """Handle preview for READ/PRUNE."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
        launch_editor,
    )

    if not app._file_system:
        return
    resource = action.params.get("resource") or action.params.get("path", "")
    try:
        content = app._file_system.read_file(resource)
    except Exception:
        content = f"--- Content for {resource} could not be retrieved ---"
    await launch_editor(app, content, suffix=pathlib.Path(resource).suffix or ".txt")


async def preview_prompt(app: ReviewerApp, action: ActionData, node: Any) -> None:
    """Handle interactive answering for PROMPT."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
        launch_editor,
    )

    message = cast(str, action.params.get("message", ""))
    response = await launch_editor(app, message, suffix=".md")

    if response is not None and await app.push_screen_wait(ConfirmScreen()):
        if response.strip() != message.strip():
            action.user_response = response.strip()
            action.modified = True
            app._refresh_node(node)
