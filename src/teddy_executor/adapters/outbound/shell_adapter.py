import os
import subprocess
from typing import Optional, Dict
from teddy_executor.core.domain.models import CommandResult
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor


class ShellAdapter(IShellExecutor):
    def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> CommandResult:
        validated_cwd = cwd
        if cwd:
            # Security Validation: Prevent command execution outside the project root.
            if os.path.isabs(cwd):
                raise ValueError(
                    f"Validation failed: `cwd` path '{cwd}' must be relative."
                )

            project_root = os.getcwd()
            full_path = os.path.realpath(os.path.join(project_root, cwd))

            if not full_path.startswith(os.path.realpath(project_root)):
                raise ValueError(
                    f"Validation failed: `cwd` path '{cwd}' is outside the project directory."
                )

            # The path is safe, use the validated full path for execution
            validated_cwd = full_path

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=False,  # `check=False` prevents raising an exception on non-zero exit codes
            cwd=validated_cwd,
            env=env,
        )
        return CommandResult(
            stdout=result.stdout, stderr=result.stderr, return_code=result.returncode
        )
