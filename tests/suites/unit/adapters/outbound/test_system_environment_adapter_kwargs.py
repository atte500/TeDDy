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
    """Verify background Popen does NOT pass explicit stdin/stdout/stderr kwargs.

    After the fix for Bug #48, background editor/diff launching must NOT pass
    explicit stdin/stdout/stderr kwargs to Popen. In Textual's TUI, sys.stdin
    lacks fileno() and passing it raises AttributeError. The child process
    inherits the parent's actual console handles automatically.
    """
    adapter = SystemEnvironmentAdapter()

    with patch("subprocess.Popen") as mock_popen:
        adapter.run_command(["echo", "test"], background=True)

    mock_popen.assert_called_once()
    _, kwargs = mock_popen.call_args
    # These kwargs must NOT be present (fix for Bug #48)
    assert "stdin" not in kwargs, (
        "stdin must NOT be passed explicitly — child inherits from parent"
    )
    assert "stdout" not in kwargs, (
        "stdout must NOT be passed explicitly — child inherits from parent"
    )
    assert "stderr" not in kwargs, (
        "stderr must NOT be passed explicitly — child inherits from parent"
    )


def test_background_launch_inherits_std_streams():
    """Background editor launch must NOT pass explicit stdio kwargs to Popen.

    After the fix for Bug #48, the subprocess inherits the parent's console
    handles automatically — no explicit stdin/stdout/stderr should be passed.
    This ensures the editor can attach to the TTY even when sys.stdin lacks
    fileno() (as in Textual's TUI).
    """
    adapter = SystemEnvironmentAdapter()

    with patch("subprocess.Popen") as mock_popen:
        adapter.run_command(["vim", "test.txt"], background=True)

    # Popen should be called with args only, no stdio kwargs
    mock_popen.assert_called_once_with(
        ["vim", "test.txt"],
    )


def test_background_launch_does_not_use_devnull():
    """Background mode must NOT pass DEVNULL for any std stream.

    After the fix for Bug #48, no explicit stdio kwargs are passed at all,
    so DEVNULL cannot appear in the call kwargs.
    """
    adapter = SystemEnvironmentAdapter()

    with patch("subprocess.Popen") as mock_popen:
        adapter.run_command(["nano", "test.txt"], background=True)

    call_kwargs = mock_popen.call_args[1]
    # After the fix, stdin/stdout/stderr should not appear in kwargs
    assert "stdin" not in call_kwargs, (
        "stdin must not be passed explicitly — child inherits from parent"
    )
    assert "stdout" not in call_kwargs, (
        "stdout must not be passed explicitly — child inherits from parent"
    )
    assert "stderr" not in call_kwargs, (
        "stderr must not be passed explicitly — child inherits from parent"
    )


def test_run_command_background_no_explicit_stdin_when_dummy_fileno():
    """Run_command(background=True) must not pass stdin/stdout/stderr when fileno missing.

    Regression test for Bug 48: In Textual TUI, sys.stdin lacks fileno().
    Passing stdin=sys.stdin to Popen raises AttributeError. The fix removes
    these kwargs entirely, letting Popen inherit handles.
    """
    import sys

    original_stdin = sys.stdin
    try:
        # Create a dummy stdin that lacks fileno (simulates Textual's wrapper)
        class DummyStdinNoFileno:
            def isatty(self):
                return False

            def fileno(self):
                raise AttributeError("DummyStdin has no fileno")

        sys.stdin = DummyStdinNoFileno()

        adapter = SystemEnvironmentAdapter()
        with patch("subprocess.Popen") as mock_popen:
            import pytest

            try:
                adapter.run_command(["echo", "test"], background=True)
            except Exception as e:
                pytest.fail(
                    f"run_command(background=True) raised an exception unexpectedly: {e}"
                )
            assert mock_popen.called, "Popen was not called"
            call_kwargs = mock_popen.call_args[1]
            assert "stdin" not in call_kwargs, (
                f"Popen should not receive stdin kwarg, got: {call_kwargs}"
            )
            assert "stdout" not in call_kwargs, (
                f"Popen should not receive stdout kwarg, got: {call_kwargs}"
            )
            assert "stderr" not in call_kwargs, (
                f"Popen should not receive stderr kwarg, got: {call_kwargs}"
            )
    finally:
        sys.stdin = original_stdin


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
