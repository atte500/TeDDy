"""Regression tests for ConsoleAskLoop stdin flush (Bug #24).

Verifies that after launching a background editor (with TTY attached),
stale terminal escape sequences are flushed from the stdin buffer before
the next prompt_toolkit read.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

# Skip the entire test module on platforms without termios (e.g., Windows).
# The production code guards termios inside _flush_stdin with a try/except,
# but the test must import it at module level for mocking.
termios = pytest.importorskip("termios")

import pytest

from teddy_executor.adapters.outbound.console_interactor_ask_loop import (
    ConsoleAskLoop,
)


@pytest.fixture
def mock_system_env():
    env = MagicMock()
    # Avoid real file I/O when _launch_editor_background is called
    env.create_temp_file.return_value = "/tmp/fake_editor.md"
    return env


@pytest.fixture
def mock_tooling():
    tooling = MagicMock()
    tooling.find_editor.return_value = ["/usr/bin/vim"]
    return tooling


@pytest.fixture
def ask_loop(mock_system_env, mock_tooling):
    return ConsoleAskLoop(mock_system_env, mock_tooling)


class TestStdinFlush:
    """Tests for _flush_stdin and its integration in the run loop."""

    PROD_PREFIX = "teddy_executor.adapters.outbound.console_interactor_ask_loop"

    def test_flush_stdin_called_after_editor_launch_in_run(self, ask_loop):
        """When user types 'e' in TTY mode, termios.tcflush must be called
        after launching the editor to clear stale escape sequences."""
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", side_effect=["e", "\n"]),
            patch.object(termios, "tcflush") as mock_tcflush,
            patch.object(ask_loop, "_read_editor_result", return_value="Done"),
        ):
            ask_loop.run("test prompt")
            mock_tcflush.assert_called_once_with(sys.stdin, termios.TCIFLUSH)

    def test_flush_stdin_called_when_in_tty_mode(self, ask_loop):
        """_flush_stdin should call termios.tcflush when stdin is a TTY."""
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch.object(termios, "tcflush") as mock_tcflush,
        ):
            ask_loop._flush_stdin()
            mock_tcflush.assert_called_once_with(sys.stdin, termios.TCIFLUSH)

    def test_flush_stdin_not_called_when_not_tty(self, ask_loop):
        """_flush_stdin should NOT call termios.tcflush when stdin is not a TTY."""
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=False),
            patch.object(termios, "tcflush") as mock_tcflush,
        ):
            ask_loop._flush_stdin()
            mock_tcflush.assert_not_called()

    def test_flush_stdin_not_called_during_normal_input(self, ask_loop):
        """When user types normal text (not 'e'), no flush should occur."""
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", return_value="hello"),
            patch.object(termios, "tcflush") as mock_tcflush,
        ):
            result = ask_loop.run("test prompt")
            assert result == "hello"
            mock_tcflush.assert_not_called()

    def test_flush_stdin_called_on_editor_relaunch(self, ask_loop):
        """When user presses Enter then 'e' to relaunch editor, flush should occur."""
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", side_effect=["e", "e", "\n"]),
            patch.object(termios, "tcflush") as mock_tcflush,
            patch.object(ask_loop, "_read_editor_result", return_value="Done"),
        ):
            ask_loop.run("test")
            assert mock_tcflush.call_count == 2, (
                "tcflush must be called for each editor launch"
            )

    def test_flush_stdin_handles_missing_termios(self, ask_loop):
        """_flush_stdin should not crash if termios is unavailable."""
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(
                "builtins.__import__",
                side_effect=ImportError("No module named termios"),
            ),
        ):
            # Should not raise any exception
            ask_loop._flush_stdin()
