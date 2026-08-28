"""Regression tests for ConsoleAskLoop stdin flush (Bug #24).

Verifies that _flush_stdin works correctly on TTY/non-TTY and handles
missing termios gracefully. Editor-integration flush tests are covered
by the synchronous editor flow in the escape-stripping test suite.
"""

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest

try:
    import termios

    _HAS_TERMIOS = True
except ImportError:
    _HAS_TERMIOS = False

try:
    import msvcrt

    _HAS_MSVCRT = True
except ImportError:
    _HAS_MSVCRT = False

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


@pytest.mark.skipif(not _HAS_TERMIOS, reason="termios not available on this platform")
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
        file_content = "User response above marker\n\n" + marker + "\n\nPrompt text"

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
        # Flush is called twice: once before reading the harvested file,
        # once after cleanup (delete + reset path).
        assert mock_flush.call_count == 2, (
            f"Expected 2 flush calls, got {mock_flush.call_count}"
        )
        mock_system_env.delete_file.assert_called_once_with("/tmp/editor.md")
        assert ask_loop._active_editor_path is None, (
            "_active_editor_path should be reset after harvest"
        )


@pytest.mark.skipif(not _HAS_MSVCRT, reason="msvcrt not available on this platform")
class TestWindowsStdinFlush:
    """Tests for the Windows (msvcrt) path of _flush_stdin.

    On Windows, termios is unavailable, so _flush_stdin should fall back to
    msvcrt.kbhit() / msvcrt.getwch() to drain the input buffer.
    """

    PROD_PREFIX = "teddy_executor.adapters.outbound.console_interactor_ask_loop"

    @pytest.fixture
    def mock_system_env(self):
        env = MagicMock()
        env.create_temp_file.return_value = "/tmp/fake_editor.md"
        return env

    @pytest.fixture
    def mock_tooling(self):
        tooling = MagicMock()
        tooling.find_editor.return_value = ["/usr/bin/vim"]
        return tooling

    @pytest.fixture
    def ask_loop(self, mock_system_env, mock_tooling):
        return ConsoleAskLoop(mock_system_env, mock_tooling)

    def test_flush_stdin_uses_msvcrt_when_termios_missing(self, ask_loop):
        """When termios is unavailable (Windows), _flush_stdin should use msvcrt
        to drain the input buffer."""
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(
                "builtins.__import__", side_effect=self._import_fails_for_termios
            ) as mock_import,
        ):
            # msvcrt.kbhit returns True once (1 char available), then False
            with patch("msvcrt.kbhit", side_effect=[True, False]) as mock_kbhit:
                with patch("msvcrt.getwch", return_value="x") as mock_getwch:
                    ask_loop._flush_stdin()

                    # If we got here without exception, the msvcrt path was used.
                    # Verify the specific functions were called.
                    # Note: __import__ may be called multiple times by the interpreter,
                    # so we check that msvcrt functions were called rather than
                    # asserting __import__ call count.
                    assert mock_kbhit.called, "msvcrt.kbhit should have been called"
                    assert mock_getwch.called, "msvcrt.getwch should have been called"

    def test_flush_stdin_noop_when_both_termios_and_msvcrt_missing(self, ask_loop):
        """When both termios and msvcrt are unavailable (rare), _flush_stdin
        should silently no-op without raising an exception."""
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch("builtins.__import__", side_effect=ImportError("no module")),
        ):
            # Should not raise any exception
            ask_loop._flush_stdin()

    @staticmethod
    def _import_fails_for_termios(name, *args, **kwargs):
        """Custom import side effect: raise ImportError for 'termios',
        allow everything else.

        Uses `importlib.__import__` to bypass the mocked `builtins.__import__`
        and prevent infinite recursion on Windows.
        """
        if name == "termios":
            raise ImportError("No module named termios")
        # Use importlib.__import__ directly to bypass the mocked builtins.__import__
        return importlib.__import__(name, *args, **kwargs)
