import os
import shlex
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
        validated_cwd = None
        project_root = os.path.realpath(os.getcwd())

        if cwd:
            # Resolve the intended cwd path. It can be absolute or relative.
            if os.path.isabs(cwd):
                validated_cwd = os.path.realpath(cwd)
            else:
                validated_cwd = os.path.realpath(os.path.join(project_root, cwd))

            # Security Validation: Prevent command execution outside the project root.
            if not validated_cwd.startswith(project_root):
                raise ValueError(
                    f"Validation failed: `cwd` path '{cwd}' resolves to '{validated_cwd}', which is outside the project directory '{project_root}'."
                )
        else:
            # Default to project root if no cwd is provided
            validated_cwd = project_root

        # Prepare environment: merge with parent environment to preserve PATH, etc.
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        # Use shlex to safely split the command string, and run with shell=False
        # This is more secure and robustly handles args with spaces or special chars.
        command_args = shlex.split(command)

        try:
            result = subprocess.run(
                command_args,
                shell=False,
                capture_output=True,
                text=True,
                check=False,
                cwd=validated_cwd,
                env=merged_env,
            )
            return CommandResult(
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
            )
        except FileNotFoundError as e:
            return CommandResult(
                stdout="",
                stderr=str(e),
                return_code=e.errno or 1,  # Use errno if available, otherwise 1
            )
