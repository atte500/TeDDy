import subprocess
from unittest.mock import patch, MagicMock  # noqa: TID251
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor


def test_execute_background_starts_popen_and_returns_pid(container):
    """
    Verifies that when background=True, ShellAdapter uses Popen and returns the PID.
    """
    adapter = container.resolve(IShellExecutor)
    mock_process = MagicMock()
    mock_process.pid = 12345

    with patch.object(adapter, "_popen", return_value=mock_process) as mock_popen:
        result = adapter.execute("sleep 10", background=True)

    mock_popen.assert_called_once()
    assert result["return_code"] == 0
    assert "[SUCCESS: Background process started with PID 12345]" in result["stdout"]
    assert result["stderr"] == ""


def test_execute_background_isolates_stdin(container):
    """
    Verifies that background processes explicitly isolate stdin to prevent
    tty resource contention or hanging in concurrent test runs.
    """
    adapter = container.resolve(IShellExecutor)
    mock_process = MagicMock()
    mock_process.pid = 9999

    with patch.object(adapter, "_popen", return_value=mock_process) as mock_popen:
        adapter.execute("sleep 10", background=True)

    mock_popen.assert_called_once()
    _, kwargs = mock_popen.call_args
    assert "stdin" in kwargs, "stdin missing from background Popen call"
    assert kwargs["stdin"] == subprocess.DEVNULL, (
        "stdin must be DEVNULL for background tasks"
    )


def test_execute_background_detaches_console_on_windows(container):
    """
    On Windows, background spawns must pass CREATE_NO_WINDOW so fire-and-forget
    children cannot mutate the parent console input mode while an interactive
    prompt session is live. On POSIX, start_new_session remains the isolation
    mechanism.
    """
    import sys

    adapter = container.resolve(IShellExecutor)
    mock_process = MagicMock()
    mock_process.pid = 4242

    with patch.object(adapter, "_popen", return_value=mock_process) as mock_popen:
        adapter.execute("sleep 10", background=True)

    _, kwargs = mock_popen.call_args
    if sys.platform == "win32":
        assert kwargs.get("creationflags") == subprocess.CREATE_NO_WINDOW, (
            "background Popen must detach from the parent console on Windows"
        )
    else:
        assert kwargs.get("start_new_session") is True
