import subprocess
from unittest.mock import patch
import pytest

from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
def test_prepare_subprocess_kwargs_stdin_is_pipe(platform):
    """
    Verify that stdin is PIPE across all platforms to provide a valid
    file descriptor for Python 3.14.2's C-level initialization, while
    still isolating the subprocess from the parent's stdin.
    """
    adapter = ShellAdapter()

    with patch("sys.platform", platform):
        kwargs = adapter._prepare_subprocess_kwargs(
            use_shell=True, cwd="/tmp", env={"A": "B"}
        )

        assert "stdin" in kwargs, f"stdin key missing on platform: {platform}"
        assert kwargs["stdin"] == subprocess.PIPE, (
            f"stdin not PIPE on platform: {platform}"
        )
