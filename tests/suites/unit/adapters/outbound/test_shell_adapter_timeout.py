import subprocess
import sys
import pytest
from unittest.mock import MagicMock, patch
from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor


@pytest.mark.anyio
async def test_execute_timeout_does_not_reset_terminal():
    """
    Regression test for Bug: TUI corruption on timeout.
    Ensures that ShellAdapter does NOT call _restore_terminal_state on timeout,
    as this corrupts the active TUI session.
    """
    adapter = ShellAdapter()

    with patch("subprocess.Popen") as mock_popen:
        process = MagicMock()
        process.pid = 999999  # Prevent os.killpg(MagicMock(), ...) which resolves to PID 1 and kills the CI worker

        process.communicate.side_effect = subprocess.TimeoutExpired(
            cmd="test", timeout=0.1
        )
        mock_popen.return_value = process

        with patch.object(adapter, "_restore_terminal_state") as mock_reset:
            # We don't care about the result, just that the reset wasn't called
            adapter.execute("sleep 5", timeout=0.1)

            assert not mock_reset.called, (
                "_restore_terminal_state was called on timeout!"
            )


def test_execute_respects_timeout(container):
    """
    Asserts that the timeout parameter is passed correctly to process.communicate.
    """
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.pid = 999999
        mock_process.communicate.return_value = ("stdout data", "stderr data")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        adapter = container.resolve(IShellExecutor)

        # Act
        timeout_threshold = 10
        adapter.execute("echo test", timeout=timeout_threshold)

        # Assert
        mock_process.communicate.assert_called_once_with(timeout=timeout_threshold)


def test_execute_works_without_timeout(container):
    """
    Asserts that the adapter still works without a timeout (defaults to None).
    """
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.pid = 999999
        mock_process.communicate.return_value = ("stdout data", "stderr data")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        adapter = container.resolve(IShellExecutor)
        adapter.execute("echo test")

        mock_process.communicate.assert_called_once_with(timeout=None)


def test_execute_handles_timeout_with_partial_output(container):
    """
    Verifies that ShellAdapter catches TimeoutExpired during communicate,
    terminates the process group, fetches partial output, and returns 124.
    """
    if sys.platform == "win32":
        pytest.skip("killpg is POSIX only")

    adapter = container.resolve(IShellExecutor)

    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.pid = 999999

        mock_process.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="sleep 10", timeout=0.1),
            ("partial stdout", "partial stderr"),
        ]
        mock_popen.return_value = mock_process

        with (
            patch("os.killpg", create=True),
            patch.object(adapter, "_restore_terminal_state") as mock_restore,
        ):
            result = adapter.execute("sleep 10", timeout=0.1)

    assert result["return_code"] == ShellAdapter.TIMEOUT_EXIT_CODE
    assert "partial stdout" in result["stdout"]
    assert "partial stderr" in result["stderr"]
    assert "[ERROR: Command timed out after 0.1 seconds]" in result["stdout"]
    # Verify terminal restore was NOT triggered (TUI safety)
    assert not mock_restore.called


def test_execute_handles_timeout_without_output(container):
    """Verifies timeout handling when no partial output is available."""
    if sys.platform == "win32":
        pytest.skip("killpg is POSIX only")

    adapter = container.resolve(IShellExecutor)

    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.pid = 999999
        mock_process.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="sleep 10", timeout=0.5),
            ("", ""),
        ]
        mock_popen.return_value = mock_process

        with (
            patch("os.killpg", create=True),
            patch.object(adapter, "_restore_terminal_state"),
        ):
            result = adapter.execute("sleep 10", timeout=0.5)

    assert result["return_code"] == ShellAdapter.TIMEOUT_EXIT_CODE
    assert result["stdout"] == "[ERROR: Command timed out after 0.5 seconds]"
    assert result["stderr"] == ""
