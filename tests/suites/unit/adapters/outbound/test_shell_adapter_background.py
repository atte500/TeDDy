from unittest.mock import patch, MagicMock
from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter


def test_execute_background_starts_popen_and_returns_pid():
    """
    Verifies that when background=True, ShellAdapter uses Popen and returns the PID.
    """
    adapter = ShellAdapter()
    mock_process = MagicMock()
    mock_process.pid = 12345

    with patch("subprocess.Popen", return_value=mock_process) as mock_popen:
        # This will fail initially because 'background' is not an accepted argument
        result = adapter.execute("sleep 10", background=True)

    mock_popen.assert_called_once()
    assert result["return_code"] == 0
    assert "[SUCCESS: Background process started with PID 12345]" in result["stdout"]
    assert result["stderr"] == ""
