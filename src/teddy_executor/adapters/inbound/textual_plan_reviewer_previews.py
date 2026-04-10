from __future__ import annotations

import os
import pathlib
from typing import TYPE_CHECKING, Any, Optional, cast

import anyio

if TYPE_CHECKING:
    from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
    from teddy_executor.core.domain.models.plan import ActionData

from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
    handle_mock_editor,
    spawn_editor,
    handle_mock_diff,
    prepare_after_file,
    harvest_edit_diff,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    ConfirmScreen,
)


async def launch_editor(
    app: "ReviewerApp",
    initial_content: str,
    suffix: str = ".txt",
    persistent_path: Optional[str] = None,
) -> Optional[str]:
    """Launches an external editor non-blockingly and waits for TUI confirmation."""
    mock_out = os.environ.get("TEDDY_TEST_MOCK_EDITOR_OUTPUT")
    if mock_out:
        return handle_mock_editor(persistent_path, mock_out)

    temp_file = persistent_path or app._system_env.create_temp_file(suffix=suffix)
    is_temp = persistent_path is None
    try:
        if is_temp or (
            not os.path.exists(temp_file) or os.path.getsize(temp_file) == 0
        ):
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(str(initial_content))

        editor_cmd = app._console_tooling.find_editor()
        if not editor_cmd:
            return None

        if os.path.exists(temp_file):
            os.chmod(temp_file, 0o644)

        spawn_editor(editor_cmd, temp_file)
        return await _confirm_and_harvest(app, temp_file, initial_content, is_temp)
    except Exception:  # nosec B110
        return None
    finally:
        if is_temp:
            app._system_env.delete_file(temp_file)


async def _confirm_and_harvest(
    app: ReviewerApp, path: Any, initial: str, is_temp: bool
) -> Optional[str]:
    confirmed = True if app.is_headless else await app.push_screen_wait(ConfirmScreen())
    if confirmed:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    if not is_temp:
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(initial))
    return None


async def do_preview_logic(app: ReviewerApp, node: Any, action: ActionData) -> None:
    """Internal logic for previewing/modifying complex actions."""
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


async def _preview_edit_diff_viewer(
    app: ReviewerApp,
    action: ActionData,
    diff_viewer: list[str],
    original: str,
    proposed: str,
) -> bool:
    import subprocess  # nosec B404

    path_str = cast(str, action.params.get("path", ""))
    before = _setup_before_file(app, path_str, original)
    p_file = action.pending_temp_file

    if p_file and isinstance(p_file, (str, os.PathLike)):
        if handle_mock_diff(p_file, before, app._system_env.delete_file):
            return True
        prepare_after_file(p_file, proposed)
        try:
            subprocess.Popen(diff_viewer + [str(before), str(p_file)])  # nosec B603
        except Exception:  # nosec B110
            pass

    confirmed = True if app.is_headless else await app.push_screen_wait(ConfirmScreen())
    app._system_env.delete_file(before)
    return _process_diff_result(confirmed, action, p_file, original, proposed)


def _setup_before_file(app: ReviewerApp, path: str, content: str) -> str:
    suffix = pathlib.Path(path).suffix or ".txt"
    before = app._system_env.create_temp_file(suffix=f".before{suffix}")
    with open(before, "w", encoding="utf-8") as f:
        f.write(content)
    os.chmod(before, 0o444)
    return before


def _process_diff_result(
    confirmed: bool, action: ActionData, p_file: Any, original: str, proposed: str
) -> bool:
    if confirmed and p_file and isinstance(p_file, (str, os.PathLike)):
        action.modified = True
        harvest_edit_diff(action, p_file, original, proposed)
        return True
    if not confirmed and p_file and isinstance(p_file, (str, os.PathLike)):
        with open(p_file, "w", encoding="utf-8") as f:
            f.write(str(proposed))
    return False


async def preview_edit(app: ReviewerApp, action: ActionData, node: Any) -> None:
    """Handle non-blocking preview for EDIT."""
    if not app._file_system:
        return
    path_str = cast(str, action.params.get("path", ""))
    suffix = pathlib.Path(path_str).suffix or ".txt"

    try:
        original = str(app._file_system.read_file(path_str))
    except Exception:
        original = ""
    proposed, _ = app._edit_simulator.simulate_edits(
        original, action.params.get("edits", [])
    )

    diff_viewer = app._console_tooling.get_diff_viewer_command()

    is_mock_path = (
        not isinstance(action.pending_temp_file, (str, os.PathLike))
        and action.pending_temp_file is not None
    )
    if not action.pending_temp_file or (
        not is_mock_path and not os.path.exists(action.pending_temp_file)
    ):
        action.pending_temp_file = app._system_env.create_temp_file(suffix=suffix)

    if diff_viewer and not is_mock_path:
        needs_refresh = await _preview_edit_diff_viewer(
            app, action, diff_viewer, original, str(proposed)
        )
        if needs_refresh:
            app._refresh_node(node)
    else:
        final = await launch_editor(
            app,
            str(proposed),
            suffix=suffix,
            persistent_path=action.pending_temp_file,
        )
        if final is not None:
            action.modified = True
            if str(final) != str(proposed):
                action.params["edits"] = [{"find": original, "replace": str(final)}]
                action.params.pop("content", None)
            app._refresh_node(node)


async def preview_create(app: ReviewerApp, action: ActionData, node: Any) -> None:
    """Handle non-blocking preview for CREATE."""
    path_str = cast(str, action.params.get("path", ""))
    content = cast(str, action.params.get("content", ""))
    suffix = pathlib.Path(path_str).suffix or ".txt"

    # Only trigger content editor for CREATE to avoid path-input deadlock.
    # Users edit the path via the parameter list in the right pane.
    if not action.pending_temp_file:
        action.pending_temp_file = app._system_env.create_temp_file(suffix=suffix)

    new_content = await launch_editor(
        app, str(content), suffix=suffix, persistent_path=action.pending_temp_file
    )

    if new_content is not None and str(new_content) != str(content):
        action.modified = True
        # Content will be harvested from pending_temp_file on submit
        app._refresh_node(node)


async def preview_text_action(app: ReviewerApp, action: ActionData, node: Any) -> None:
    """Handle non-blocking preview for EXECUTE/RESEARCH."""
    key = "command" if action.type == "EXECUTE" else "queries"
    content = action.params.get(key, "")
    suffix = ".sh" if action.type == "EXECUTE" else ".txt"

    # Ensure a persistent path exists for the harvest
    if not action.pending_temp_file:
        action.pending_temp_file = app._system_env.create_temp_file(suffix=suffix)

    final = await launch_editor(
        app, str(content), suffix=suffix, persistent_path=action.pending_temp_file
    )

    if final is not None:
        action.modified = True
        if str(final) != str(content):
            action.params[key] = str(final)
        app._refresh_node(node)


async def preview_readonly(app: ReviewerApp, action: ActionData) -> None:
    """Handle non-blocking preview for READ/PRUNE (read-only)."""
    if not app._file_system:
        return
    resource = action.params.get("resource") or action.params.get("path", "")
    try:
        content = app._file_system.read_file(resource)
    except Exception:
        content = f"--- Content for {resource} could not be retrieved ---"

    temp_file = app._system_env.create_temp_file(
        suffix=pathlib.Path(resource).suffix or ".txt"
    )
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(content)
        # Lock file as read-only
        os.chmod(temp_file, 0o444)
        editor_cmd = app._console_tooling.find_editor()
        if editor_cmd:
            # We don't use the deferred harvest pattern for READ/PRUNE as they are truly read-only
            with app.suspend():
                await anyio.to_thread.run_sync(
                    app._system_env.run_command, editor_cmd + [temp_file]
                )
            # Short wait for user to finish reading before we delete
            if not app.is_headless:
                await app.push_screen_wait(ConfirmScreen("Finished viewing?"))
    finally:
        app._system_env.delete_file(temp_file)


async def preview_prompt(app: ReviewerApp, action: ActionData, node: Any) -> None:
    """Handle non-blocking interactive answering for PROMPT."""

    message = cast(str, action.params.get("prompt", ""))
    marker = app.INSTRUCTION_MARKER
    response = getattr(action, "user_response", None) or ""
    initial_content = f"{response}{marker}\n\n{message}\n"

    # Ensure a persistent path exists for the harvest
    if not action.pending_temp_file:
        action.pending_temp_file = app._system_env.create_temp_file(suffix=".md")

    # For PROMPT, closing the editor is the submission intent
    final = await launch_editor(
        app, initial_content, suffix=".md", persistent_path=action.pending_temp_file
    )

    if final is not None:
        marker_clean = marker.strip()
        if marker_clean in final:
            final = final.split(marker_clean)[0].strip()
        else:
            final = final.strip()

        if final and final != message.strip():
            action.modified = True
            action.user_response = final
            app._refresh_node(node)
