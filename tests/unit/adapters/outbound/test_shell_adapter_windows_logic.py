from unittest.mock import patch
import pytest
from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter


@pytest.fixture
def adapter():
    return ShellAdapter()


def test_windows_wraps_complex_single_line_commands(adapter):
    """
    BUG: Single-line chained commands are not currently wrapped on Windows.
    Desired: Trigger on is_complex, not just is_multiline.
    """
    cmd = "echo start && false"
    with patch("sys.platform", "win32"):
        prepared, use_shell = adapter._prepare_command_for_platform(cmd)

        assert use_shell is True
        # Desired: should be wrapped with FAILED_COMMAND
        assert "FAILED_COMMAND:" in prepared
        # Chained commands in safe_line should have escaped operators
        assert "echo start ^&^& false" in prepared


def test_windows_uses_exit_not_exit_b(adapter):
    """
    BUG: exit /b 1 is used currently, which is unreliable in cmd /c.
    Desired: Use exit 1 for robust process termination.
    """
    cmd = "echo first\nexit 1"
    with patch("sys.platform", "win32"):
        prepared, _ = adapter._prepare_command_for_platform(cmd)

        assert '& exit 1"' in prepared
    assert "exit /b 1" not in prepared


def test_windows_escapes_redirection_operators(adapter):
    """
    BUG: > and < are currently not escaped in the FAILED_COMMAND echo.
    Desired: Escape > and < to prevent output redirection in diagnostics.
    """
    cmd = "echo something > file.txt\nexit 1"
    with patch("sys.platform", "win32"):
        prepared, _ = adapter._prepare_command_for_platform(cmd)

        # The FAILED_COMMAND part should have escaped redirection
        assert "FAILED_COMMAND: echo something ^> file.txt" in prepared
