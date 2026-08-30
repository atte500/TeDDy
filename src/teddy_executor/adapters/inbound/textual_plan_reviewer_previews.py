from __future__ import annotations

import logging
import os
import pathlib
import sys
import tempfile
import urllib.request
from typing import TYPE_CHECKING, Any, Optional, cast


if TYPE_CHECKING:
    from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
    from teddy_executor.core.domain.models.plan import ActionData

from teddy_executor.adapters.inbound.textual_plan_reviewer_editor import (
    _flush_stdin,
    _is_cli_editor,
    _restore_foreground_process_group,
    _restore_terminal_cooked_mode,
    launch_editor,
    preview_edit_diff_viewer,
    spawn_editor,
)

logger = logging.getLogger(__name__)


async def do_preview_logic(app: ReviewerApp, node: Any, action: ActionData) -> None:
    """Internal logic for previewing/modifying complex actions."""
    if action.type == "CREATE":
        await preview_create(app, action, node)
    elif action.type == "EDIT":
        await preview_edit(app, action, node)
    elif action.type in ("EXECUTE", "RESEARCH"):
        await preview_text_action(app, action, node)
    elif action.type == "READ":
        await preview_readonly(app, action)


# Diff viewer orchestration moved to textual_plan_reviewer_editor.py


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
        needs_refresh = await preview_edit_diff_viewer(
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
            if "edits" not in action.modified_fields:
                action.modified_fields.append("edits")
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
        if "content" not in action.modified_fields:
            action.modified_fields.append("content")
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
        if key not in action.modified_fields:
            action.modified_fields.append(key)
        if str(final) != str(content):
            action.params[key] = str(final)
        app._refresh_node(node)


def _fetch_url_content(url: str) -> str:
    """Fetch content from a URL using urllib.

    Falls back gracefully on network errors. Used by preview_readonly()
    to open URL-based READ action resources in an external editor.
    """
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            content = response.read().decode("utf-8", errors="replace")
        return content
    except Exception as e:
        logger.debug("Failed to fetch URL content for READ preview: %s", e)
        raise


async def preview_readonly(app: ReviewerApp, action: ActionData) -> None:
    """Handle non-blocking preview for READ (read-only).

    Opens the resource in an external editor without harvesting content.
    Resources can be local file paths or URLs (http/https).
    - CLI editors: subprocess.run() inside app.suspend()
    - GUI editors: Popen (background) — no ConfirmScreen (read-only, no save needed)
    - URLs: content is fetched and written to a temp file for viewing
    """
    resource = action.params.get("resource") or action.params.get("path", "")
    if not resource:
        return

    # Check for editor availability
    editor_cmd = app._console_tooling.find_editor()
    if not editor_cmd:
        app.notify("No editor configured. Please configure one in .teddy/config.yaml")
        return

    editor_name = os.path.basename(editor_cmd[0])
    app.notify(f"Opening Editor: {editor_name}")

    # Handle URL resources: fetch content and write to a temp file
    is_url = resource.startswith(("http://", "https://"))
    if is_url:
        try:
            content = _fetch_url_content(resource)
        except Exception:
            app.notify(f"Failed to fetch URL: {resource}")
            return
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            prefix="teddy_read_url_",
            delete=False,
            encoding="utf-8",
        )
        temp_file.write(content)
        temp_path = temp_file.name
        temp_file.close()
    else:
        if not os.path.exists(resource):
            app.notify(f"Resource not found: {resource}")
            return
        temp_path = resource

    if _is_cli_editor(editor_cmd):
        import subprocess  # noqa: PLC0415

        logger.debug("Opening READ file (CLI editor): %s", temp_path)
        with app.suspend():
            subprocess.run(  # noqa: B603
                editor_cmd + [temp_path],
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
            _restore_foreground_process_group()
            _restore_terminal_cooked_mode()
        _flush_stdin()
    else:
        logger.debug("Opening READ file (GUI editor): %s", temp_path)
        spawn_editor(editor_cmd, temp_path)
        # No ConfirmScreen for READ — content is not harvestable and
        # the user is viewing, not editing.

    # Clean up temp file if it was created for a URL
    if is_url:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


async def view_details_handler(app: "ReviewerApp") -> None:
    """Implementation for viewing action logs."""
    from textual.widgets import Tree
    from teddy_executor.core.domain.models.plan import ActionData
    from teddy_executor.adapters.inbound.textual_plan_reviewer_execution import (
        format_action_log,
    )

    tree = app.query_one(Tree)
    node = tree.cursor_node
    if not node or not node.data:
        return

    action = node.data
    if not isinstance(action, ActionData) or not action.executed:
        return

    if action.action_log:
        log_content = format_action_log(action.action_log)
        temp_file = app._system_env.create_temp_file(suffix=".md")
        app._log_preview_files.append(temp_file)
        await launch_editor(
            app,
            log_content,
            suffix=".md",
            persistent_path=temp_file,
            skip_confirm=True,
        )


async def view_plan_handler(app: "ReviewerApp") -> None:
    """Implementation for viewing the full plan."""
    content: Optional[str] = None
    plan_path = app.plan.plan_path
    if plan_path and app._file_system:
        try:
            content = app._file_system.read_file(plan_path)
        except Exception as e:
            logger.debug("Failed to read plan file for viewing: %s", e)
    if not content:
        content = app.plan.raw_content
    if not content:
        content = f"# Plan: {app.plan.title}\n\n{app.plan.rationale}\n\n"

    if content:
        # If we have a persistent path, we use it. We skip confirmation because
        # 'view' is intended to be a read-only or informational action.
        await launch_editor(
            app,
            content,
            suffix=".md",
            persistent_path=plan_path,
            skip_confirm=True,
        )


async def add_message_handler(app: "ReviewerApp") -> None:
    """Implementation for adding user instruction message.

    Uses an external editor to compose the message, then shows a ConfirmScreen
    before storing. This defers LLM processing (harvest) until the user confirms
    or cancels, preventing the TUI freeze that occurs when content is processed
    immediately after editor exit.
    """
    # Create persistent file path if not already set
    if not hasattr(app, "_pending_message_file") or app._pending_message_file is None:
        app._pending_message_file = app._system_env.create_temp_file(suffix=".md")
        app.plan.metadata["pending_message_file"] = app._pending_message_file

    current_message = app._user_message_cache
    if current_message is None:
        current_message = app.plan.metadata.get("user_request") or ""
        if app.INSTRUCTION_MARKER not in current_message:
            current_message += app.INSTRUCTION_MARKER

    new_message = await launch_editor(
        app,
        current_message,
        suffix=".md",
        persistent_path=app._pending_message_file,
        skip_confirm=True,
    )
    if new_message is not None and new_message != current_message:
        app._user_message_cache = new_message
