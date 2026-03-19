import pytest
import sys
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor


@pytest.fixture
def adapter(container):
    return container.resolve(IShellExecutor)


def test_execute_multi_line_command_fails_fast_and_reports_command(adapter):
    """
    Scenario: Multi-line command with internal failure
    Given a command string with three lines where the second one fails
    When executed via the ShellAdapter
    Then the return_code must be non-zero
    And the failed_command must be correctly identified
    """
    # Use cross-platform python commands to trigger failure
    cmd = (
        f"{sys.executable} -c \"print('line1')\"\n"
        f'{sys.executable} -c "import sys; sys.exit(1)"\n'
        f"{sys.executable} -c \"print('line3')\""
    )

    result = adapter.execute(cmd)

    assert result["return_code"] != 0
    # We expect the wrapper to have stopped execution before line 3
    assert "line3" not in result["stdout"]
    assert "line1" in result["stdout"]

    # This is the core requirement of Scenario 4
    assert "failed_command" in result
    assert "sys.exit(1)" in result["failed_command"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX specific test")
def test_posix_specific_failure_behavior(adapter):
    """Verify that POSIX trap/set -e behavior works as expected."""
    cmd = "echo first\nfalse\necho second"
    result = adapter.execute(cmd)
    assert result["return_code"] != 0
    assert "second" not in result["stdout"]
    assert result.get("failed_command") == "false"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX specific test")
def test_posix_chained_failure_behavior(adapter):
    """Verify that granular failure works even with && chaining."""
    # Our function-based trap successfully isolates sub-commands even in chains.
    cmd = "echo start && false && echo end"
    result = adapter.execute(cmd)
    assert result["return_code"] != 0
    assert "end" not in result["stdout"]
    assert result.get("failed_command") == "false"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows specific test")
def test_windows_specific_failure_behavior(adapter):
    """Verify that Windows ERRORLEVEL check behavior works as expected."""
    cmd = "echo first\nexit /b 1\necho second"
    result = adapter.execute(cmd)
    assert result["return_code"] != 0
    assert "second" not in result["stdout"]
    assert result.get("failed_command") == "exit /b 1"
