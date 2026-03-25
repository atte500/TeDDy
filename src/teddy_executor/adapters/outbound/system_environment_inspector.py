import os
import platform
import sys
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
        return {
            "os_name": platform.system(),
            "os_version": platform.release(),
            "python_version": sys.version,
            "cwd": os.getcwd(),
            "shell": os.getenv("SHELL", "unknown"),
        }

    def get_git_status(self) -> Optional[str]:
        """
        Gathers the current Git status of the working directory.
        """
        return None
