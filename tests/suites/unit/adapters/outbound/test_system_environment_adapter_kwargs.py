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
    """Verify background Popen does NOT use DEVNULL for stdin or any stream.

    After the fix for Bug #23, background editor/diff launching must inherit
    the parent process's stdin/stdout/stderr to allow terminal-based tools
    (vim, nvim, nano) to attach to the TTY. This test verifies that stdin
    is sys.stdin (not DEVNULL), confirming the stream inheritance works.
    """
    import sys

    adapter = SystemEnvironmentAdapter()

    with patch("subprocess.Popen") as mock_popen:
        adapter.run_command(["echo", "test"], background=True)

    mock_popen.assert_called_once()
    _, kwargs = mock_popen.call_args
    assert "stdin" in kwargs, "stdin missing from background Popen call"
    assert kwargs["stdin"] is sys.stdin, (
        "stdin must be sys.stdin (inherited from parent) for background "
        "editor/diff launching, not DEVNULL"
    )
    assert "stdout" in kwargs, "stdout missing from background Popen call"
    assert kwargs["stdout"] is sys.stdout, (
        "stdout must be sys.stdout (inherited from parent)"
    )
    assert "stderr" in kwargs, "stderr missing from background Popen call"
    assert kwargs["stderr"] is sys.stderr, (
        "stderr must be sys.stderr (inherited from parent)"
    )


def test_background_launch_inherits_std_streams():
    """Background editor launch must inherit parent std streams for TTY access.

    When running terminal-based editors (vim, nvim, nano) in background mode,
    the subprocess must inherit stdin/stdout/stderr from the parent process
    instead of binding them to DEVNULL. This ensures the editor can attach to
    the TTY and display its UI.
    """
    import sys

    adapter = SystemEnvironmentAdapter()

    with patch("subprocess.Popen") as mock_popen:
        adapter.run_command(["vim", "/tmp/test.txt"], background=True)

    mock_popen.assert_called_once_with(
        ["vim", "/tmp/test.txt"],
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


def test_background_launch_does_not_use_devnull():
    """Background mode must NOT pass DEVNULL for any std stream.

    Negative assertion: confirm DEVNULL is not passed as stdin, stdout, or stderr.
    """
    adapter = SystemEnvironmentAdapter()

    with patch("subprocess.Popen") as mock_popen:
        adapter.run_command(["nano", "/tmp/test.txt"], background=True)

    call_kwargs = mock_popen.call_args[1]
    assert call_kwargs.get("stdin") is not subprocess.DEVNULL, (
        "stdin must not be DEVNULL — editor needs TTY"
    )
    assert call_kwargs.get("stdout") is not subprocess.DEVNULL, (
        "stdout must not be DEVNULL — editor needs TTY"
    )
    assert call_kwargs.get("stderr") is not subprocess.DEVNULL, (
        "stderr must not be DEVNULL — editor needs TTY"
    )


def test_synchronous_run_unchanged():
    """Synchronous mode should still use DEVNULL for stdin only.

    Synchronous commands (subprocess.run) should be unaffected by the fix:
    they don't need TTY and should continue to pipe stdin from DEVNULL.
    """
    adapter = SystemEnvironmentAdapter()

    with patch("subprocess.run") as mock_run:
        adapter.run_command(["cat", "/dev/null"], background=False)

    mock_run.assert_called_once_with(
        ["cat", "/dev/null"], check=True, stdin=subprocess.DEVNULL
    )
