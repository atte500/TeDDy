from unittest.mock import patch
import pytest
from teddy_executor.adapters.outbound.shell_command_builder import ShellCommandBuilder


@pytest.fixture
def builder():
    return ShellCommandBuilder(platform="win32")


def test_windows_command_wrapping_includes_parentheses(builder):
    """
    Verify that multi-line commands on Windows are wrapped in parentheses
    to enforce correct operator precedence (|| vs &&).
    """
    command = "echo line1\necho line2"

    # We mock shutil.which to ensure it doesn't try to find 'echo' as a file.
    with patch("shutil.which", return_value=None):
        wrapped_cmd, use_shell = builder.prepare(command)

        # Expected implementation (WITH FIX):
        # (line1 || handler1) && (line2 || handler2)

        assert use_shell is True
        # Check for parentheses and 'call' prefix around the first command segment
        assert "(call echo line1 ||" in wrapped_cmd
        # Check for parentheses and 'call' prefix around the second command segment
        assert "&& (call echo line2 ||" in wrapped_cmd
        # Ensure the final parenthesis is present
        assert wrapped_cmd.endswith('")')


def test_windows_command_wrapping_isolates_exit_commands(builder):
    """
    Verify that 'exit' commands on Windows are wrapped in 'cmd /c'
    instead of 'call' to ensure they don't terminate the parent shell.
    """
    command = "echo hello\nexit /b 1\necho world"

    with patch("shutil.which", return_value=None):
        wrapped_cmd, _ = builder.prepare(command)

        # Non-exit command should use 'call'
        assert "(call echo hello ||" in wrapped_cmd
        # Exit command should use 'cmd /c' and be quoted
        assert '&& (cmd /c "exit /b 1" ||' in wrapped_cmd
        # Ensure the failure reporter is still there
        assert 'echo FAILED_COMMAND: exit /b 1 >&2 & exit 1")' in wrapped_cmd


def test_windows_wraps_complex_single_line_commands(builder):
    """
    Verify that single-line chained commands are wrapped on Windows
    to ensure granular failure reporting.
    """
    cmd = "echo start && false"
    prepared, use_shell = builder.prepare(cmd)

    assert use_shell is True
    # Should be wrapped with FAILED_COMMAND diagnostic logic
    assert "FAILED_COMMAND:" in prepared
    # Chained commands in safe_line should have escaped operators
    assert "echo start ^&^& false" in prepared


def test_windows_uses_exit_not_exit_b(builder):
    """
    Verify that 'exit 1' is used instead of 'exit /b 1' for robust
    process termination within cmd /c.
    """
    cmd = "echo first\nexit 1"
    prepared, _ = builder.prepare(cmd)

    assert '& exit 1"' in prepared
    assert "exit /b 1" not in prepared


def test_windows_escapes_redirection_and_carets(builder):
    """
    Verify that redirection operators (> and <) and carets (^) are escaped
    in the diagnostic echo.
    """
    cmd = "echo ^something > file.txt\nexit 1"
    prepared, _ = builder.prepare(cmd)

    # The FAILED_COMMAND part should have escaped redirection and carets
    assert "FAILED_COMMAND: echo ^^something ^> file.txt" in prepared
