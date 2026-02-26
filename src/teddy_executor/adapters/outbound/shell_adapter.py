import os
import shutil
import subprocess
import sys
from typing import Optional, Dict, List

from teddy_executor.core.domain.models.shell_output import ShellOutput
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor


class ShellAdapter(IShellExecutor):
    def _validate_cwd(self, cwd: Optional[str]) -> str:
        """Validates and resolves the working directory."""
        project_root = os.path.realpath(os.getcwd())
        if not cwd:
            return project_root

        validated_cwd = (
            os.path.realpath(cwd)
            if os.path.isabs(cwd)
            else os.path.realpath(os.path.join(project_root, cwd))
        )

        if not validated_cwd.startswith(project_root):
            raise ValueError(
                f"Validation failed: `cwd` path '{cwd}' resolves to '{validated_cwd}', which is outside the project directory '{project_root}'."
            )
        return validated_cwd

    def _prepare_command_for_platform(
        self, command: str
    ) -> tuple[str | List[str], bool]:
        """Determines command arguments and shell usage based on the OS."""
        if sys.platform == "win32":
            first_word = command.strip().split()[0]
            if shutil.which(first_word):
                return command, False  # It's a file, run directly.
            return command, True  # It's a shell built-in.
        # On POSIX, always use the shell to support pipes, globbing, etc.
        return command, True

    def _log_debug_pre_execution(
        self, command: str, command_args: str | List[str], cwd: str, use_shell: bool
    ):
        if os.getenv("TEDDY_DEBUG"):
            print("--- ShellAdapter Debug ---", file=sys.stderr)
            print(f"Platform: {sys.platform}", file=sys.stderr)
            print(f"Original command: {command!r}", file=sys.stderr)
            print(f"Tokenized/Command args: {command_args}", file=sys.stderr)
            print(f"CWD: {cwd}", file=sys.stderr)
            print(f"Shell: {use_shell}", file=sys.stderr)
            print("--------------------------", file=sys.stderr)

    def _log_debug_result(self, result: subprocess.CompletedProcess):
        if os.getenv("TEDDY_DEBUG"):
            print("--- ShellAdapter Result ---", file=sys.stderr)
            print(f"Return Code: {result.returncode}", file=sys.stderr)
            print(f"STDOUT:\n{result.stdout}", file=sys.stderr)
            print(f"STDERR:\n{result.stderr}", file=sys.stderr)
            print("---------------------------", file=sys.stderr)

    def _log_debug_error(self, error: Exception):
        if os.getenv("TEDDY_DEBUG"):
            print("--- ShellAdapter Error ---", file=sys.stderr)
            print(f"Error: {error}", file=sys.stderr)
            print("--------------------------", file=sys.stderr)

    def _run_subprocess(
        self,
        command_args: str | List[str],
        use_shell: bool,
        cwd: str,
        env: Dict[str, str],
    ) -> ShellOutput:
        """Executes the command in a subprocess and handles errors."""
        try:
            result = subprocess.run(
                command_args,
                shell=use_shell,
                capture_output=True,
                text=True,
                check=False,
                cwd=cwd,
                env=env,
            )
            self._log_debug_result(result)
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
            }
        except (FileNotFoundError, OSError) as e:
            self._log_debug_error(e)
            return {
                "stdout": "",
                "stderr": str(e),
                "return_code": getattr(e, "errno", 1),
            }

    def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> ShellOutput:
        validated_cwd = self._validate_cwd(cwd)
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        command_args, use_shell = self._prepare_command_for_platform(command)

        self._log_debug_pre_execution(command, command_args, validated_cwd, use_shell)

        return self._run_subprocess(command_args, use_shell, validated_cwd, merged_env)
