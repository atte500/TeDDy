import subprocess
from unittest.mock import patch
import pytest

from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
def test_prepare_subprocess_kwargs_isolates_stdin_universally(platform):
    """
    Verify that stdin is isolated (DEVNULL) across all platforms
    to prevent concurrent test workers from crashing.
    """
    adapter = ShellAdapter()

    with patch("sys.platform", platform):
        kwargs = adapter._prepare_subprocess_kwargs(
            use_shell=True, cwd="/tmp", env={"A": "B"}
        )

        assert "stdin" in kwargs, f"stdin key missing on platform: {platform}"
        assert kwargs["stdin"] == subprocess.DEVNULL, (
            f"stdin not DEVNULL on platform: {platform}"
        )
