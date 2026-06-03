import sys
import pytest
from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter
from teddy_executor.adapters.outbound.shell_command_builder import ShellCommandBuilder


pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="UNIX-specific interactive prompt detection",
)


class TestUnixInteractivePromptDetection:
    """Unit tests for ShellAdapter detection of interactive-prompt commands on UNIX."""

    def test_interactive_command_returns_failure_message(self):
        """
        Red phase: demand that ShellAdapter returns the standardized
        "FAILURE: Interactive prompt detected" message when a command
        would normally read from TTY.

        With stdin redirection to DEVNULL, `input()` raises EOFError
        immediately. The adapter should detect this pattern and return
        the standardized failure instead of raw stderr.
        """
        adapter = ShellAdapter(command_builder=ShellCommandBuilder())

        result = adapter.execute(
            "python -c \"input('> ')\"",
        )

        assert "FAILURE: Interactive prompt detected" in result["stdout"], (
            f"Expected standardized failure message, got stdout={result['stdout']!r}, "
            f"stderr={result['stderr']!r}, return_code={result['return_code']}"
        )
        assert result["return_code"] != 0, (
            "Interactive commands must return a non-zero exit code"
        )

    def test_non_interactive_command_does_not_trigger_failure(self):
        """
        Sanity check: a benign echo command should NOT produce the
        interactive-failure message.
        """
        adapter = ShellAdapter(command_builder=ShellCommandBuilder())

        result = adapter.execute("echo hello")

        assert "FAILURE: Interactive prompt detected" not in result["stdout"]
        assert result["return_code"] == 0

    def test_shell_read_p_detected_as_interactive(self):
        """
        Fast-fail: shell `read -p` with stdin=DEVNULL must exit
        immediately with non-zero return code (no hang).
        Standardized message is not expected here because this
        shell builtin produces no stderr on some platforms.
        """
        adapter = ShellAdapter(command_builder=ShellCommandBuilder())

        result = adapter.execute("read -p 'Enter value: ' value")

        assert result["return_code"] != 0, (
            f"Expected non-zero exit for interactive command, "
            f"got stdout={result['stdout']!r}, stderr={result['stderr']!r}"
        )

    def test_getpass_detected_as_interactive(self):
        """
        Red phase: `getpass.getpass()` with stdin=DEVNULL should
        produce the standardized interactive-failure message.
        """
        adapter = ShellAdapter(command_builder=ShellCommandBuilder())

        result = adapter.execute(
            'python -c "import getpass; getpass.getpass()"',
        )

        assert "FAILURE: Interactive prompt detected" in result["stdout"], (
            f"Expected standardized failure message, got stdout={result['stdout']!r}, "
            f"stderr={result['stderr']!r}, return_code={result['return_code']}"
        )
        assert result["return_code"] != 0
