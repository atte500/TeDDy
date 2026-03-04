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

    def run_command(self, args: List[str], check: bool = True) -> None:
        subprocess.run(args, check=check)  # nosec B603

    def create_temp_file(self, suffix: str = "", mode: str = "w") -> str:
        with tempfile.NamedTemporaryFile(mode=mode, suffix=suffix, delete=False) as tf:
            return tf.name

    def delete_file(self, path: str) -> None:
        if os.path.exists(path):
            os.unlink(path)
