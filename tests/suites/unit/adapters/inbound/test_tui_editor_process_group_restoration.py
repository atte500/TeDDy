"""
Regression test: Ensure foreground process group and terminal cooked mode
are restored inside the app.suspend() block, before _flush_stdin() outside.

The bug was that after subprocess.run inside app.suspend(), the child
process (vim) may leave the foreground process group in an inconsistent
state, causing Textual's start_application_mode() NOP tcsetattr check
to fail, resulting in console drop and hang.

This test verifies the call order:
SUSPEND_ENTER -> RESTORE_PGRP -> RESTORE_TTY -> SUSPEND_EXIT -> FLUSH
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from teddy_executor.adapters.inbound.textual_plan_reviewer_editor import (
    launch_editor,
    _flush_stdin,
    _restore_foreground_process_group,
    _restore_terminal_cooked_mode,
)


@pytest.mark.anyio
async def test_restoration_functions_called_inside_suspend():
    """Verify that _restore_foreground_process_group and
    _restore_terminal_cooked_mode are called INSIDE the suspend block,
    and _flush_stdin is called OUTSIDE."""
    call_order: list[str] = []

    app = MagicMock()
    app.is_headless = False
    app._console_tooling.find_editor.return_value = ["vim"]
    app.INSTRUCTION_MARKER = "<!-- marker -->"
    app.notify = MagicMock()

    # Create a proper mock for the suspend context manager
    suspend_cm = MagicMock()
    suspend_cm.__enter__.side_effect = lambda: call_order.append("SUSPEND_ENTER")
    suspend_cm.__exit__.side_effect = lambda *args: call_order.append("SUSPEND_EXIT")
    app.suspend = MagicMock(return_value=suspend_cm)

    # Track the restoration functions and flush
    original_fgp = _restore_foreground_process_group
    original_tty = _restore_terminal_cooked_mode
    original_flush = _flush_stdin

    def tracked_fgp():
        call_order.append("RESTORE_PGRP")
        original_fgp()

    def tracked_tty():
        call_order.append("RESTORE_TTY")
        original_tty()

    def tracked_flush():
        call_order.append("FLUSH_CALL")
        original_flush()

    with patch(
        "teddy_executor.adapters.inbound.textual_plan_reviewer_editor._restore_foreground_process_group",
        side_effect=tracked_fgp,
    ), patch(
        "teddy_executor.adapters.inbound.textual_plan_reviewer_editor._restore_terminal_cooked_mode",
        side_effect=tracked_tty,
    ), patch(
        "teddy_executor.adapters.inbound.textual_plan_reviewer_editor._flush_stdin",
        side_effect=tracked_flush,
    ):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("edited content")
            temp_path = f.name
        app._system_env.create_temp_file.return_value = temp_path
        app._system_env.delete_file = MagicMock()

        with patch("subprocess.run", return_value=MagicMock()):
            await launch_editor(app, "initial content")

        os.remove(temp_path)

    expected_order = [
        "SUSPEND_ENTER",
        "RESTORE_PGRP",
        "RESTORE_TTY",
        "SUSPEND_EXIT",
        "FLUSH_CALL",
    ]

    # Filter to only the tracked events
    filtered_order = [c for c in call_order if c in expected_order]

    assert filtered_order == expected_order, (
        f"Call order mismatch.\nExpected: {expected_order}\nGot: {filtered_order}\nFull: {call_order}"
    )


@pytest.mark.anyio
async def test_restoration_functions_graceful_in_non_tty():
    """Verify that the restoration functions don't crash in a non-TTY environment."""
    # Already proven by verify_shadow_fix.py, but re-test for production code
    _restore_foreground_process_group()
    _restore_terminal_cooked_mode()
    # If we reach here without exception, the test passes


def test_restore_functions_imported():
    """Verify the new functions are importable from the production module."""
    assert callable(_restore_foreground_process_group)
    assert callable(_restore_terminal_cooked_mode)