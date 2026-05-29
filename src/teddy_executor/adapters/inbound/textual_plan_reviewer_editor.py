from __future__ import annotations

import logging
import os
import pathlib
from typing import TYPE_CHECKING, Any, Optional, cast

if TYPE_CHECKING:
    from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
    from teddy_executor.core.domain.models.plan import ActionData

from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    ConfirmScreen,
)

logger = logging.getLogger(__name__)


# Low-level editor helpers
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
        subprocess.Popen(  # nosec B603
            cmd + [str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.debug("Failed to spawn editor: %s", e)


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


async def launch_editor(
    app: "ReviewerApp",
    initial_content: str,
    suffix: str = ".txt",
    persistent_path: Optional[str] = None,
    skip_confirm: bool = False,
) -> Optional[str]:
    """Launches an external editor non-blockingly and waits for TUI confirmation."""
    mock_out = os.environ.get("TEDDY_TEST_MOCK_EDITOR_OUTPUT")
    temp_file = persistent_path or app._system_env.create_temp_file(suffix=suffix)
    is_temp = persistent_path is None

    if mock_out:
        handle_mock_editor(temp_file, mock_out)
        confirmed = (
            True
            if app.is_headless or skip_confirm
            else await app.push_screen_wait(ConfirmScreen())
        )
        return mock_out if confirmed else None

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
        return await _confirm_and_harvest(
            app, temp_file, initial_content, is_temp, skip_confirm=skip_confirm
        )
    except Exception as e:
        logger.debug("Failed to launch editor flow: %s", e)
        return None
    finally:
        if is_temp:
            app._system_env.delete_file(temp_file)


async def _confirm_and_harvest(
    app: ReviewerApp, path: Any, initial: str, is_temp: bool, skip_confirm: bool = False
) -> Optional[str]:
    confirmed = (
        True
        if app.is_headless or skip_confirm
        else await app.push_screen_wait(ConfirmScreen())
    )
    if confirmed:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    if not is_temp:
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(initial))
    return None


async def preview_edit_diff_viewer(
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
            subprocess.Popen(  # nosec B603
                diff_viewer + [str(before), str(p_file)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.debug("Failed to launch diff viewer: %s", e)

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
        if "edits" not in action.modified_fields:
            action.modified_fields.append("edits")
        harvest_edit_diff(action, p_file, original, proposed)
        return True
    if not confirmed and p_file and isinstance(p_file, (str, os.PathLike)):
        with open(p_file, "w", encoding="utf-8") as f:
            f.write(str(proposed))
    return False


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
        from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
            _apply_param_edit,
        )

        _apply_param_edit(action, key, new_val)
        action.modified = True
        if key and key not in action.modified_fields:
            action.modified_fields.append(key)
        app._refresh_node(node)
        update_fn(app, action)


async def handle_edit_action(
    app: "ReviewerApp", node: Any, action: Any, update_fn: Any
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
