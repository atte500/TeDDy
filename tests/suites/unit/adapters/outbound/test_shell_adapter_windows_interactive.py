"""
Unit tests for ShellAdapter interactive prompt detection on Windows.

These tests verify that ShellAdapter correctly detects interactive prompts
on Windows by testing the detection methods directly:
- _detect_interactive_prompt static method with Windows-specific patterns
- _handle_timeout method with simulated TimeoutExpired and stderr patterns

All tests avoid banned MagicMock/patch and use only create_autospec
with direct method invocation (no popen constructor injection).
"""

import subprocess
import sys
from unittest.mock import create_autospec

import pytest

from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter
from teddy_executor.adapters.outbound.shell_command_builder import ShellCommandBuilder


class TestDetectInteractivePrompt:
    """Direct tests for ShellAdapter._detect_interactive_prompt static method."""

    @pytest.mark.parametrize(
        "stderr,expected",
        [
            # Windows interactive patterns that should be detected
            ("Input required", True),
            ("Input required\nMore stderr", True),
            ("Unexpected EOF while reading input", True),
            ("cannot read input", True),
            # Cross-platform pattern from Python input() with DEVNULL
            ("EOFError", True),
            ("EOFError while reading input", True),
            # Non-interactive patterns that should NOT match
            ("", False),
            ("Hello World", False),
            ("Permission denied", False),
            ("File not found", False),
            ("KeyError: 'missing'", False),
        ],
    )
    def test_static_detection_patterns(self, stderr: str, expected: bool):
        """Verify _detect_interactive_prompt matches/non-matches as expected."""
        assert ShellAdapter._detect_interactive_prompt(stderr) == expected


class TestHandleTimeout:
    """Direct tests for ShellAdapter._handle_timeout instance method."""

    def _make_timeout_process(
        self,
        return_value: tuple[str, str],
        returncode: int = 1,
        pid: int = 999999,
    ) -> subprocess.Popen:
        """Create an auto-specced Popen that simulates post-timeout output."""
        proc = create_autospec(subprocess.Popen, instance=True)
        proc.pid = pid
        proc.returncode = returncode
        proc.communicate.return_value = return_value
        return proc

    def test_timeout_with_input_required_detected(self):
        """
        When _handle_timeout gets stderr containing 'Input required',
        it must return the standardized interactive prompt message.
        """
        adapter = ShellAdapter(command_builder=ShellCommandBuilder(platform="win32"))
        process = self._make_timeout_process(
            return_value=("partial stdout", "Input required\nMore stderr"),
        )

        result = adapter._handle_timeout(process, 0.5)

        assert ShellAdapter.INTERACTIVE_PROMPT_MESSAGE in result["stdout"], (
            f"Expected interactive prompt message, got stdout={result['stdout']!r}"
        )
        assert result["return_code"] == ShellAdapter.TIMEOUT_EXIT_CODE

    def test_timeout_with_unexpected_eof_detected(self):
        """
        When _handle_timeout gets stderr containing 'Unexpected EOF',
        it must return the standardized interactive prompt message.
        """
        adapter = ShellAdapter(command_builder=ShellCommandBuilder(platform="win32"))
        process = self._make_timeout_process(
            return_value=("", "Unexpected EOF while reading input"),
        )

        result = adapter._handle_timeout(process, 0.5)

        assert ShellAdapter.INTERACTIVE_PROMPT_MESSAGE in result["stdout"], (
            f"Expected interactive prompt message, got stdout={result['stdout']!r}"
        )

    def test_timeout_with_non_interactive_stderr_returns_timeout_message(self):
        """
        When _handle_timeout gets non-interactive stderr, it must return
        the standard timeout message, not the interactive prompt message.
        """
        adapter = ShellAdapter(command_builder=ShellCommandBuilder(platform="win32"))
        process = self._make_timeout_process(
            return_value=("some stdout content", "regular error: file not found"),
        )

        result = adapter._handle_timeout(process, 0.5)

        assert ShellAdapter.INTERACTIVE_PROMPT_MESSAGE not in result["stdout"], (
            "Non-interactive timeout should NOT return interactive prompt message"
        )
        assert "timed out" in result["stdout"], (
            f"Expected timeout message, got stdout={result['stdout']!r}"
        )
        assert "some stdout content" in result["stdout"]

    def test_cmd_c_wrapper_exit_propagation(self):
        """
        Simulate a cmd /c wrapped command that fails due to interactive
        input; _handle_timeout must detect 'Input required from terminal'.
        """
        adapter = ShellAdapter(command_builder=ShellCommandBuilder(platform="win32"))
        process = self._make_timeout_process(
            return_value=("", "Input required from terminal"),
        )

        result = adapter._handle_timeout(process, 0.5)

        assert ShellAdapter.INTERACTIVE_PROMPT_MESSAGE in result["stdout"], (
            f"Expected interactive prompt message, got stdout={result['stdout']!r}"
        )
        assert result["return_code"] != 0


class TestRealWindowsSubprocess:
    """Real process test that only runs on Windows CI."""

    @pytest.mark.skipif(
        sys.platform != "win32",
        reason="Real subprocess test only runs on Windows CI",
    )
    def test_real_windows_interactive_command(self):
        """
        Real set /p with stdin=DEVNULL should fail with interactive prompt message.
        Validates the actual subprocess behavior on Windows CI.
        """
        adapter = ShellAdapter(command_builder=ShellCommandBuilder(platform="win32"))

        result = adapter.execute('cmd /c "set /p test_var="')

        assert ShellAdapter.INTERACTIVE_PROMPT_MESSAGE in result["stdout"], (
            f"Real Windows interactive command should be detected, "
            f"got stdout={result['stdout']!r}, stderr={result['stderr']!r}, "
            f"return_code={result['return_code']}"
        )
        assert result["return_code"] != 0, (
            "Interactive commands must return non-zero exit code"
        )
