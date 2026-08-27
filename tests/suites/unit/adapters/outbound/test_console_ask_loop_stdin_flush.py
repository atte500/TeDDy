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

    def test_flush_stdin_called_during_harvest(self, ask_loop, mock_system_env):
        """When _handle_empty_input is called with _active_editor_path set,
        the file is read, content harvested, temp file deleted, and
        _flush_stdin is called."""
        from unittest.mock import mock_open, patch

        # Arrange
        ask_loop._active_editor_path = "/tmp/editor.md"
        marker = "<!-- Please enter your response above this line. -->"
        file_content = (
            "User response above marker\n\n" + marker + "\n\nPrompt text"
        )

        with (
            patch.object(ask_loop, "_flush_stdin") as mock_flush,
            patch("builtins.open", mock_open(read_data=file_content)),
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
        ):
            # Act
            result = ask_loop._handle_empty_input("test prompt")

        # Assert
        assert result == "User response above marker", (
            f"Expected 'User response above marker', got: {repr(result)}"
        )
        mock_flush.assert_called_once()
        mock_system_env.delete_file.assert_called_once_with("/tmp/editor.md")
        assert ask_loop._active_editor_path is None, (
            "_active_editor_path should be reset after harvest"
        )
