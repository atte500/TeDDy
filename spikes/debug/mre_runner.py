import sys
import subprocess
import pytest
from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter

# The verified fix: Redirect stdin to DEVNULL on all platforms.
original_prepare = ShellAdapter._prepare_subprocess_kwargs

def patched_prepare_subprocess_kwargs(self, use_shell, cwd, env):
    kwargs = original_prepare(self, use_shell, cwd, env)
    # Always set stdin to DEVNULL to prevent Windows xdist worker crashes
    # caused by concurrent subprocesses inheriting the same stdin pipe handle.
    kwargs["stdin"] = subprocess.DEVNULL
    return kwargs

ShellAdapter._prepare_subprocess_kwargs = patched_prepare_subprocess_kwargs

if __name__ == "__main__":
    sys.exit(pytest.main(sys.argv[1:]))