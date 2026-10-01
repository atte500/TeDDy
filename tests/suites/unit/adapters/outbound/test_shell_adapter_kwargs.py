import subprocess
import sys

import pytest

from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
def test_prepare_subprocess_kwargs_stdin_is_pipe(platform, monkeypatch):
    """
    Verify that stdin is PIPE across all platforms to provide a valid
    file descriptor for Python 3.14.2's C-level initialization, while
    still isolating the subprocess from the parent's stdin.
    """
    adapter = ShellAdapter()

    monkeypatch.setattr(sys, "platform", platform)
    kwargs = adapter._prepare_subprocess_kwargs(
        use_shell=True, cwd="/tmp", env={"A": "B"}
    )

    assert "stdin" in kwargs, f"stdin key missing on platform: {platform}"
    assert kwargs["stdin"] == subprocess.PIPE, f"stdin not PIPE on platform: {platform}"


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
def test_prepare_subprocess_kwargs_preexec_fn_shield_on_posix(platform, monkeypatch):
    """
    Characterization: the foreground execute path shields the child from
    the terminal's process-group SIGINT on POSIX via a preexec_fn that
    detaches it into a new session (setsid/setpgrp) with the SIGTTOU/
    SIGTTIN suspension guards — functionally equivalent to
    start_new_session=True for session detachment (and strictly superior:
    the flag lacks the suspension guards). On win32 there is no POSIX
    process-group equivalent: the kwarg is absent and graceful handling
    is best-effort, flag-based only (the second-signal force-kill is the
    escape hatch for hung children).
    """
    adapter = ShellAdapter()

    monkeypatch.setattr(sys, "platform", platform)
    kwargs = adapter._prepare_subprocess_kwargs(
        use_shell=True, cwd="/tmp", env={"A": "B"}
    )

    if platform == "win32":
        assert "preexec_fn" not in kwargs, (
            f"preexec_fn must be absent on platform: {platform}"
        )
    else:
        assert "preexec_fn" in kwargs, (
            f"preexec_fn shield missing on platform: {platform}"
        )
        assert callable(kwargs["preexec_fn"]), (
            f"preexec_fn must be callable on platform: {platform}"
        )
