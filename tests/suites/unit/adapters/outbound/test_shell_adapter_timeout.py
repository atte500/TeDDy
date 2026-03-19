import subprocess
from unittest.mock import patch, Mock
from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor


def test_execute_respects_timeout(container):
    """
    Asserts that the timeout parameter is passed correctly to subprocess.run.
    We don't test actual subprocess timeouts here (Scenario 2),
    just that the parameter is accepted and propagated.
    """
    with patch("subprocess.run") as mock_run:
        # Setup mock_run to return a successful CompletedProcess
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        adapter = container.resolve(IShellExecutor)

        # Act
        timeout_threshold = 10
        adapter.execute("echo test", timeout=timeout_threshold)

        # Assert
        # We check the arguments passed to subprocess.run
        _, kwargs = mock_run.call_args
        assert kwargs.get("timeout") == timeout_threshold


def test_execute_works_without_timeout(container):
    """
    Asserts that the adapter still works without a timeout (defaults to None).
    """
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        adapter = container.resolve(IShellExecutor)
        adapter.execute("echo test")

        _, kwargs = mock_run.call_args
        assert kwargs.get("timeout") is None


def test_execute_handles_timeout_with_partial_output(container):
    """
    Verifies that ShellAdapter catches TimeoutExpired, decodes partial bytes,
    and returns return_code 124 with a warning.
    """
    adapter = container.resolve(IShellExecutor)

    # Simulate TimeoutExpired with partial output in bytes
    # subprocess.run returns TimeoutExpired with bytes even if text=True
    timeout_err = subprocess.TimeoutExpired(
        cmd="sleep 10", timeout=0.1, output=b"partial stdout", stderr=b"partial stderr"
    )

    with patch("subprocess.run", side_effect=timeout_err):
        result = adapter.execute("sleep 10", timeout=0.1)

    assert result["return_code"] == ShellAdapter.TIMEOUT_EXIT_CODE
    assert "partial stdout" in result["stdout"]
    assert "partial stderr" in result["stderr"]
    assert "[ERROR: Command timed out after 0.1 seconds]" in result["stdout"]


def test_execute_handles_timeout_without_output(container):
    """Verifies timeout handling when no partial output is available."""
    adapter = container.resolve(IShellExecutor)
    timeout_err = subprocess.TimeoutExpired(cmd="sleep 10", timeout=0.5)

    with patch("subprocess.run", side_effect=timeout_err):
        result = adapter.execute("sleep 10", timeout=0.5)

    assert result["return_code"] == ShellAdapter.TIMEOUT_EXIT_CODE
    assert result["stdout"] == "[ERROR: Command timed out after 0.5 seconds]"
    assert result["stderr"] == ""
