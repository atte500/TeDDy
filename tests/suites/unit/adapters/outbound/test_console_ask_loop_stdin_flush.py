"""Regression tests for ConsoleAskLoop stdin flush (Bug #24).

Verifies that _flush_stdin works correctly on TTY/non-TTY and handles
missing termios gracefully. Editor-integration flush tests are covered
by the synchronous editor flow in the escape-stripping test suite.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

termios = pytest.importorskip("termios")

from teddy_executor.adapters.outbound.console_interactor_ask_loop import (
    ConsoleAskLoop,
)


@pytest.fixture
def mock_system_env():
    env = MagicMock()
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

    def test_flush_stdin_handles_missing_termios(self, ask_loop):
        """_flush_stdin should not crash if termios is unavailable."""
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(
                "builtins.__import__",
                side_effect=ImportError("No module named termios"),
            ),
        ):
            ask_loop._flush_stdin()
