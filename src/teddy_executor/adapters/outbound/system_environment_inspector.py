import os
import platform
import subprocess  # nosec B404
import sys
from datetime import datetime
from typing import Optional

from teddy_executor.core.ports.outbound.environment_inspector import (
    IEnvironmentInspector,
)


class SystemEnvironmentInspector(IEnvironmentInspector):
    """
    An adapter that inspects the real system environment using standard
    Python libraries.
    """

    def get_environment_info(self) -> dict[str, str]:
        """
        Gathers key information about the system environment.
        """
        now = datetime.now()
        return {
            "os_name": platform.system(),
            "os_version": platform.release(),
            "python_version": sys.version,
            "cwd": os.getcwd(),
            "shell": os.getenv("SHELL", "unknown"),
            "current_date": now.strftime("%Y-%m-%d"),
            "current_time": now.strftime("%H:%M:%S"),
        }

    def get_git_status(self) -> Optional[str]:
        """
        Gathers the current Git status of the working directory.
        """
        try:
            result = subprocess.run(  # nosec B603 B607
                ["git", "status", "-s"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.rstrip() if result.stdout else ""
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
