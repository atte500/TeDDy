from unittest.mock import patch
import pytest
from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter


@pytest.fixture
def adapter():
    return ShellAdapter()


def test_windows_command_wrapping_includes_parentheses(adapter):
    """
    Verify that multi-line commands on Windows are wrapped in parentheses
    to enforce correct operator precedence (|| vs &&).
    """
    command = "echo line1\necho line2"

    # We mock sys.platform to 'win32' to trigger the Windows-specific logic
    # and we mock shutil.which to ensure it doesn't try to find 'echo' as a file.
    with patch("sys.platform", "win32"), patch("shutil.which", return_value=None):
        wrapped_cmd, use_shell = adapter._prepare_command_for_platform(command)

        # Expected implementation (WITH FIX):
        # (line1 || handler1) && (line2 || handler2)

        assert use_shell is True
        # Check for parentheses and 'call' prefix around the first command segment
        assert "(call echo line1 ||" in wrapped_cmd
        # Check for parentheses and 'call' prefix around the second command segment
        assert "&& (call echo line2 ||" in wrapped_cmd
        # Ensure the final parenthesis is present
        assert wrapped_cmd.endswith('")')


def test_windows_wraps_complex_single_line_commands(adapter):
    """
    Verify that single-line chained commands are wrapped on Windows
    to ensure granular failure reporting.
    """
    cmd = "echo start && false"
    with patch("sys.platform", "win32"):
        prepared, use_shell = adapter._prepare_command_for_platform(cmd)

        assert use_shell is True
        # Should be wrapped with FAILED_COMMAND diagnostic logic
        assert "FAILED_COMMAND:" in prepared
        # Chained commands in safe_line should have escaped operators
        assert "echo start ^&^& false" in prepared


def test_windows_uses_exit_not_exit_b(adapter):
    """
    Verify that 'exit 1' is used instead of 'exit /b 1' for robust
    process termination within cmd /c.
    """
    cmd = "echo first\nexit 1"
    with patch("sys.platform", "win32"):
        prepared, _ = adapter._prepare_command_for_platform(cmd)

        assert '& exit 1"' in prepared
        assert "exit /b 1" not in prepared


def test_windows_escapes_redirection_and_carets(adapter):
    """
    Verify that redirection operators (> and <) and carets (^) are escaped
    in the diagnostic echo.
    """
    cmd = "echo ^something > file.txt\nexit 1"
    with patch("sys.platform", "win32"):
        prepared, _ = adapter._prepare_command_for_platform(cmd)

        # The FAILED_COMMAND part should have escaped redirection and carets
        assert "FAILED_COMMAND: echo ^^something ^> file.txt" in prepared
