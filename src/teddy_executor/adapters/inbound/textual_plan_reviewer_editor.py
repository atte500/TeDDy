from __future__ import annotations

import logging
import os
import pathlib
import re
import sys
import tempfile
from typing import TYPE_CHECKING, Any, Optional, cast


if TYPE_CHECKING:
    from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
    from teddy_executor.core.domain.models.plan import ActionData

from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    ConfirmScreen,
)

logger = logging.getLogger(__name__)

# Regex to match ANSI escape sequences (SGR codes, OSC sequences, etc.)
_ESCAPE_SEQUENCE_RE = re.compile(
    r"\x1b\[[0-9;]*[a-zA-Z]"
    r"|\x1b\][^\x1b]*(?:\x1b\\|\x07)"
    r"|(?![\d;,])]10;(?:\d+;)?rgb:[\da-fA-F/]+(?::$|[a-zA-Z])?(?:\x1b\\|\x07)?"
)

# Set of known CLI (terminal-based) editors that need suspend/resume handover
_CLI_EDITORS: set[str] = {
    "vim",
    "nvim",
    "vi",
    "nano",
    "micro",
    "emacs",
    "pico",
    "helix",
    "hx",
    "kak",
}


def reconstruct_from_diff(edited_text: str) -> str:
    """Reconstruct the final content from an annotated diff file.

    Rules:
    - Lines starting with '---' or '+++' (file headers): ignored
    - Lines starting with '@@': ignored (hunk headers)
    - Lines starting with '-': REMOVED LINES -- discarded entirely.
        Even if the user modified them, they don't appear in output.
    - Lines starting with '+': ADDED LINES -- kept, with the '+' prefix stripped.
    - Lines with NO prefix: CONTEXT LINES -- kept as-is.
    """
    result: list[str] = []
    for line in edited_text.splitlines(keepends=True):
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("@@"):
            continue
        if line.startswith("-"):
            continue
        if line.startswith("+"):
            result.append(line[1:])  # strip '+'
        else:
            result.append(line)  # context lines kept
    return "".join(result)


def _generate_annotated_diff_content(
    original: str,
    proposed: str,
    path_str: str = "",
) -> str:
    """Generate a single annotated diff file content with minimal header.

    Produces a unified diff showing the entire file as context (not just
    3 lines around changes), with a vim modeline as the first line to
    force diff syntax highlighting.
    """
    import difflib  # noqa: PLC0415

    fromlines = original.splitlines(keepends=True)
    tolines = proposed.splitlines(keepends=True)
    full_context = len(fromlines) + len(tolines)

    diff_lines = list(
        difflib.unified_diff(
            fromlines,
            tolines,
            fromfile=f"{path_str} (original)",
            tofile=f"{path_str} (proposed)",
            n=full_context,
        )
    )
    diff_text = "".join(diff_lines)

    return diff_text


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
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
    except Exception as e:
        logger.debug("Failed to spawn editor: %s", e)


def _is_cli_editor(editor_cmd: Optional[list[str]]) -> bool:
    """Return True if the resolved editor command is a known terminal (CLI) editor.

    CLI editors require suspend/resume + subprocess.run() for proper terminal
    handover. GUI editors (code, cursor) use the existing Popen + ConfirmScreen path.
    """
    if not editor_cmd:
        return False
    basename = os.path.basename(editor_cmd[0])
    return basename in _CLI_EDITORS


def _is_vim_editor(editor_cmd: Optional[list[str]]) -> bool:
    """Return True if the editor is a vim variant (vim, nvim, vi).

    Vim/Neovim require explicit `syntax on` and `filetype plugin on` to enable
    syntax highlighting by default. This function detects vim-based editors so
    we can append the necessary -c flags.
    """
    if not editor_cmd:
        return False
    basename = os.path.basename(editor_cmd[0])
    return basename.lower() in {"vim", "nvim", "vi"}


def _flush_stdin() -> None:
    """Flush stale escape sequences from the TTY input buffer after editor exit.

    Handles POSIX (termios), Windows (msvcrt), and gracefully degrades on
    environments without a TTY (CI, headless servers).
    """
    try:
        import termios  # noqa: PLC0415

        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except ImportError:
        try:
            import msvcrt  # noqa: PLC0415

            while msvcrt.kbhit():
                msvcrt.getwch()
        except ImportError:
            pass
    except Exception:
        pass


def _restore_terminal_cooked_mode() -> None:
    """Restore terminal to cooked mode after subprocess.run inside suspend.

    Mirrors the emergency TTY restore found in SystemEnvironmentAdapter.run_command().
    A child process (like vim) may leave the terminal in raw mode after exit.
    This ensures cooked mode (ICANON | ECHO) is re-established before
    Textual's resume_application_mode() runs.
    """
    try:
        if sys.stdin.isatty():
            fd = sys.stdin.fileno()
            import termios  # noqa: PLC0415

            attrs = termios.tcgetattr(fd)
            attrs[0] |= termios.ICRNL
            attrs[3] |= termios.ICANON | termios.ECHO
            termios.tcsetattr(fd, termios.TCSAFLUSH, attrs)
    except Exception as e:
        logger.debug("Failed to restore terminal cooked mode: %s", e)


def _restore_foreground_process_group() -> None:
    """Restore the foreground process group after subprocess.run inside suspend.

    When a child process (like vim) runs with a real TTY, it may call
    tcsetpgrp() to claim the foreground. On exit, it should restore the
    original pgrp, but macOS may not do this correctly. This function
    explicitly restores the TeDDy process to the foreground so that
    Textual's start_application_mode() NOP tcsetattr check can succeed.
    """
    if sys.platform == "win32":
        return
    try:
        fd = sys.stdin.fileno()
        if os.isatty(fd):
            os.tcsetpgrp(fd, os.getpgrp())
    except Exception as e:
        logger.debug("Failed to restore foreground process group: %s", e)


def _strip_escape_sequences(text: str) -> str:
    """Remove ANSI escape sequences and OSC control sequences from text."""
    return _ESCAPE_SEQUENCE_RE.sub("", text)


def handle_mock_diff(p_file: Any) -> bool:
    """Helper for mock diff output in tests.

    Writes mock output to the given file if TEDDY_TEST_MOCK_EDITOR_OUTPUT
    env var is set. The caller is responsible for any file cleanup.
    """
    mock_out = os.environ.get("TEDDY_TEST_MOCK_EDITOR_OUTPUT")
    if mock_out:
        with open(p_file, "w", encoding="utf-8") as f:
            f.write(mock_out)
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

    if mock_out:
        temp_file = persistent_path or app._system_env.create_temp_file(suffix=suffix)
        is_temp = persistent_path is None
        handle_mock_editor(temp_file, mock_out)
        confirmed = (
            True
            if app.is_headless or skip_confirm
            else await app.push_screen_wait(ConfirmScreen())
        )
        return mock_out if confirmed else None

    # Check for editor availability BEFORE creating a temp file.
    # If no editor is configured, notify and return early without any file operations.
    # This prevents a FileNotFoundError on Windows where /tmp does not exist.
    editor_cmd = app._console_tooling.find_editor()
    if not editor_cmd:
        app.notify("No editor configured. Please configure one in .teddy/config.yaml")
        return None

    temp_file = persistent_path or app._system_env.create_temp_file(suffix=suffix)
    is_temp = persistent_path is None

    try:
        if is_temp or (
            not os.path.exists(temp_file) or os.path.getsize(temp_file) == 0
        ):
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(str(initial_content))

        if os.path.exists(temp_file):
            os.chmod(temp_file, 0o644)

        # Show notification before spawning
        editor_name = (
            os.path.basename(editor_cmd[0])
            if isinstance(editor_cmd, list) and editor_cmd
            else "editor"
        )
        app.notify(f"Opening Editor: {editor_name}")

        if _is_cli_editor(editor_cmd):
            import subprocess  # noqa: PLC0415

            logger.info("Opening Editor (sync): %s", editor_name)
            # Build command: add vim-specific flags to enable syntax highlighting
            cmd = list(editor_cmd)
            if _is_vim_editor(cmd):
                cmd.extend(["-c", "syntax on", "-c", "filetype plugin on"])
            cmd.append(temp_file)
            with app.suspend():
                subprocess.run(  # noqa: B603
                    cmd,
                    stdin=sys.stdin,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                )
                # Restore foreground process group before Textual resumes
                _restore_foreground_process_group()
                # Restore cooked mode as secondary safety measure
                _restore_terminal_cooked_mode()
            _flush_stdin()
            with open(temp_file, "r", encoding="utf-8") as f:
                content = f.read()
            content = _strip_escape_sequences(content)
            marker = app.INSTRUCTION_MARKER.strip()
            if marker in content:
                content = content.split(marker)[0].strip()
            return content if content else None
        else:
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
    path_str = cast(str, action.params.get("path", ""))
    p_file = action.pending_temp_file

    if p_file and isinstance(p_file, (str, os.PathLike)):
        # For CLI editors, use the annotated single-file diff flow.
        # The 'before' file is NOT created — annotated diff replaces it.
        if _is_cli_editor(diff_viewer):
            import subprocess  # noqa: PLC0415

            # Handle mock output first (before creating any temp files)
            mock_out = os.environ.get("TEDDY_TEST_MOCK_EDITOR_OUTPUT")
            if mock_out:
                with open(p_file, "w", encoding="utf-8") as f:
                    f.write(mock_out)
                return True

            prepare_after_file(p_file, proposed)

            # Generate annotated diff content
            diff_content = _generate_annotated_diff_content(
                original, proposed, path_str
            )

            # Create temp .diff file with annotated content
            annotated_file = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".diff",
                prefix="teddy_edit_diff_",
                delete=False,
                encoding="utf-8",
            )
            annotated_path = annotated_file.name
            annotated_file.write(diff_content)
            annotated_file.close()

            editor_name = os.path.basename(diff_viewer[0])
            app.notify(f"Opening Editor: {editor_name}")

            try:
                with app.suspend():
                    # Build command: use editor WITHOUT diff flags — single annotated file
                    cmd = list(diff_viewer[:1])
                    if _is_vim_editor(cmd):
                        cmd.extend(["-c", "syntax on", "-c", "filetype plugin on"])
                    cmd.append(annotated_path)
                    subprocess.run(  # noqa: B603
                        cmd,
                        stdin=sys.stdin,
                        stdout=sys.stdout,
                        stderr=sys.stderr,
                    )
                    _restore_foreground_process_group()
                    _restore_terminal_cooked_mode()
                # Flush stdin after suspend to prevent stale keystrokes from
                # leaking into Textual's event loop.
                _flush_stdin()

                # Read back and reconstruct
                with open(annotated_path, "r", encoding="utf-8") as f:
                    edited_content = f.read()
                final_content = reconstruct_from_diff(edited_content)

                # Harvest if content changed
                if final_content and final_content != proposed:
                    action.params["edits"] = [
                        {"find": original, "replace": final_content}
                    ]
                    action.params.pop("content", None)

                return True
            except Exception as e:
                logger.debug("Failed to run annotated diff editor: %s", e)
                return False
            finally:
                try:
                    os.unlink(annotated_path)
                except OSError:
                    pass

        # GUI editor: launch in background, show ConfirmScreen
        before = _setup_before_file(app, path_str, original)
        if handle_mock_diff(p_file):
            app._system_env.delete_file(before)
            return True
        prepare_after_file(p_file, proposed)
        try:
            app._system_env.run_command(
                diff_viewer + [str(before), str(p_file)],
                background=True,
            )
        except Exception as e:
            logger.debug("Failed to launch diff viewer: %s", e)

        confirmed = (
            True if app.is_headless else await app.push_screen_wait(ConfirmScreen())
        )
        app._system_env.delete_file(before)
        return _process_diff_result(confirmed, action, p_file, original, proposed)

    # No pending_temp_file — return False without cleanup
    return False


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
