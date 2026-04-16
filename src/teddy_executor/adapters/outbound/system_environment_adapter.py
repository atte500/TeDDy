import os
import shutil
import subprocess  # nosec
import tempfile
from typing import List, Optional
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


class SystemEnvironmentAdapter(ISystemEnvironment):
    def which(self, command: str) -> Optional[str]:
        return shutil.which(command)

    def get_env(self, key: str) -> Optional[str]:
        return os.getenv(key)

    def run_command(
        self, args: List[str], check: bool = True, background: bool = False
    ) -> None:
        """Wraps subprocess.run (synchronous) or subprocess.Popen (background)."""
        import sys

        if background:
            # We don't wait for the result
            subprocess.Popen(  # nosec B603
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return

        try:
            subprocess.run(args, check=check)  # nosec B603
        finally:
            # Emergency TTY restore for Darwin/Linux.
            # We guard against running during tests to prevent SIGTTOU hangs in CI workers.
            if (
                sys.platform != "win32"
                and sys.stdin.isatty()
                and "PYTEST_CURRENT_TEST" not in os.environ
            ):
                try:
                    import termios

                    fd = sys.stdin.fileno()
                    attrs = termios.tcgetattr(fd)
                    attrs[0] |= termios.ICRNL
                    attrs[3] |= termios.ICANON | termios.ECHO
                    termios.tcsetattr(fd, termios.TCSAFLUSH, attrs)
                except Exception:  # nosec B110
                    pass

    def create_temp_file(self, suffix: str = "", mode: str = "w") -> str:
        with tempfile.NamedTemporaryFile(mode=mode, suffix=suffix, delete=False) as tf:
            return tf.name

    def delete_file(self, path: str) -> None:
        if os.path.exists(path):
            os.unlink(path)
