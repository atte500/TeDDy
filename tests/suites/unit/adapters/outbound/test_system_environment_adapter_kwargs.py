import subprocess
from unittest.mock import patch
from teddy_executor.adapters.outbound.system_environment_adapter import (
    SystemEnvironmentAdapter,
)


def test_run_command_foreground_isolates_stdin():
    """Verify synchronous subprocess.run gets stdin=subprocess.DEVNULL."""
    adapter = SystemEnvironmentAdapter()

    with patch("subprocess.run") as mock_run:
        adapter.run_command(["echo", "test"], background=False)

    mock_run.assert_called_once()
    _, kwargs = mock_run.call_args
    assert "stdin" in kwargs, "stdin missing from subprocess.run call"
    assert kwargs["stdin"] == subprocess.DEVNULL, (
        "stdin must be DEVNULL for foreground tasks"
    )


def test_run_command_background_isolates_stdin():
    """Verify asynchronous subprocess.Popen gets stdin=subprocess.DEVNULL."""
    adapter = SystemEnvironmentAdapter()

    with patch("subprocess.Popen") as mock_popen:
        adapter.run_command(["echo", "test"], background=True)

    mock_popen.assert_called_once()
    _, kwargs = mock_popen.call_args
    assert "stdin" in kwargs, "stdin missing from background Popen call"
    assert kwargs["stdin"] == subprocess.DEVNULL, (
        "stdin must be DEVNULL for background tasks"
    )
