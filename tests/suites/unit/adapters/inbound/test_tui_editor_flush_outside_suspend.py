"""
Regression test: Ensure _flush_stdin() is called outside the app.suspend() block.

The bug was that _flush_stdin() was called INSIDE the suspend block, causing
termios.tcflush to flush terminal response data that Textual's resume
mechanism needed to read.

This test verifies the call order: SUSPEND_ENTER -> SUSPEND_EXIT -> flush.
If a future refactor moves _flush_stdin back inside suspend, this test fails.
"""

import os
import tempfile
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from teddy_executor.adapters.inbound.textual_plan_reviewer_editor import (
    launch_editor,
    _flush_stdin,
)


@pytest.mark.anyio
async def test_flush_called_after_suspend_exit():
    """Verify that _flush_stdin() is called after the app.suspend() context exits."""
    call_order: list[str] = []

    app = MagicMock()
    app.is_headless = False
    app._console_tooling.find_editor.return_value = ["vim"]
    app.INSTRUCTION_MARKER = "<!-- marker -->"
    app.notify = MagicMock()

    @contextmanager
    def tracking_suspend():
        call_order.append("SUSPEND_ENTER")
        try:
            yield
        finally:
            call_order.append("SUSPEND_EXIT")

    app.suspend = tracking_suspend

    # We need to trace the flush call. Since _flush_stdin is defined in
    # the same module, we can use a wrapper to track it.
    original_flush = _flush_stdin

    def tracked_flush():
        call_order.append("FLUSH_CALL")
        original_flush()

    with patch(
        "teddy_executor.adapters.inbound.textual_plan_reviewer_editor._flush_stdin",
        side_effect=tracked_flush,
    ):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("edited content")
            temp_path = f.name
        app._system_env.create_temp_file.return_value = temp_path
        app._system_env.delete_file = MagicMock()

        with patch("subprocess.run", return_value=MagicMock()):
            result = await launch_editor(app, "initial content")

    os.remove(temp_path)

    # Inspect call order
    flush_idx = call_order.index("FLUSH_CALL")
    exit_idx = call_order.index("SUSPEND_EXIT")
    assert flush_idx > exit_idx, (
        f"_flush_stdin() called before suspend exit! Call order: {call_order}"
    )
    # Because is_temp=True, launch_editor overwrites the temp file with
    # initial_content before the editor runs. The mock editor does nothing,
    # so the content remains the initial content.
    assert result == "initial content", f"Expected 'initial content', got {result}"


@pytest.mark.anyio
async def test_flush_called_after_suspend_exit_with_exception():
    """If an exception occurs inside suspend, ensure flush is NOT called (no false positive)."""
    call_order: list[str] = []

    app = MagicMock()
    app.is_headless = False
    app._console_tooling.find_editor.return_value = ["vim"]
    app.INSTRUCTION_MARKER = "<!-- marker -->"
    app.notify = MagicMock()

    @contextmanager
    def tracking_suspend():
        call_order.append("SUSPEND_ENTER")
        try:
            yield
        finally:
            call_order.append("SUSPEND_EXIT")

    app.suspend = tracking_suspend

    original_flush = _flush_stdin

    def tracked_flush():
        call_order.append("FLUSH_CALL")
        original_flush()

    with patch(
        "teddy_executor.adapters.inbound.textual_plan_reviewer_editor._flush_stdin",
        side_effect=tracked_flush,
    ):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("content")
            temp_path = f.name
        app._system_env.create_temp_file.return_value = temp_path
        app._system_env.delete_file = MagicMock()

        # Simulate subprocess.run raising an exception
        with patch("subprocess.run", side_effect=Exception("test error")):
            result = await launch_editor(app, "test")

    os.remove(temp_path)

    assert result is None, "Should return None on exception"
    # If the exception occurs inside the suspend block, we never reach flush
    assert "FLUSH_CALL" not in call_order, (
        "flush should not be called if exception inside suspend"
    )
    assert "SUSPEND_EXIT" in call_order, "suspend exit should still be called"
