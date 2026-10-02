import os
import shutil
import subprocess  # nosec
import tempfile
from typing import List, Optional
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.utils.terminal import restore_cooked_mode


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
            # Mirrors spawn_editor() in textual_plan_reviewer_editor.py: on
            # Windows, detach fire-and-forget GUI launches (diff viewers,
            # editors) from the parent console so their launcher chains cannot
            # mutate our console input mode while an interactive prompt is
            # live. CREATE_NO_WINDOW gives the child its own invisible console.
            popen_kwargs: dict = {}
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            subprocess.Popen(  # nosec B603
                args,
                **popen_kwargs,
            )
            return

        try:
            subprocess.run(args, check=check, stdin=subprocess.DEVNULL)  # nosec B603
        finally:
            # Emergency TTY restore for Darwin/Linux, delegated to the shared
            # helper (the single source of truth; the TTY/test guard lives inside
            # it so no SIGTTOU hangs occur under the CI workers).
            restore_cooked_mode()

    def create_temp_file(self, suffix: str = "", mode: str = "w") -> str:
        with tempfile.NamedTemporaryFile(mode=mode, suffix=suffix, delete=False) as tf:
            return tf.name

    def delete_file(self, path: str) -> None:
        if os.path.exists(path):
            os.unlink(path)
