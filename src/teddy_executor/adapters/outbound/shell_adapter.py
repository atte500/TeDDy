import os
import re
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

    def _decompose_command(self, command: str) -> List[str]:
        """Decomposes a command string into atomic steps, respecting quotes."""
        pattern = r'("[^"]*"|\'[^\']*\'|&&|\n|[^\n&"\']+)'
        tokens = re.findall(pattern, command.strip())

        atomic_commands: List[str] = []
        current_cmd_parts: List[str] = []
        for token in tokens:
            if token in ("\n", "&&"):
                if current_cmd_parts:
                    atomic_commands.append("".join(current_cmd_parts).strip())
                    current_cmd_parts = []
            else:
                current_cmd_parts.append(token)

        if current_cmd_parts:
            atomic_commands.append("".join(current_cmd_parts).strip())

        return [c for c in atomic_commands if c]

    def _handle_directives(
        self, cmd: str, current_cwd: str, current_env: Dict[str, str]
    ) -> str:
        """Processes cd/export/set directives and returns the updated CWD."""
        if cmd.startswith("cd "):
            path = cmd[3:].strip().strip("'").strip('"')
            return self._validate_cwd(
                path if os.path.isabs(path) else os.path.join(current_cwd, path)
            )

        if cmd.startswith("export "):
            kv = cmd[7:].strip()
            if "=" in kv:
                k, v = kv.split("=", 1)
                current_env[k.strip()] = v.strip().strip("'").strip('"')
        elif sys.platform == "win32" and cmd.startswith("set "):
            kv = cmd[4:].strip()
            if "=" in kv:
                k, v = kv.split("=", 1)
                current_env[k.strip()] = v.strip().strip("'").strip('"')

        return current_cwd

    def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> ShellOutput:
        current_cwd = self._validate_cwd(cwd)
        current_env = os.environ.copy()
        if env:
            current_env.update(env)

        total_stdout: List[str] = []
        total_stderr: List[str] = []

        for cmd in self._decompose_command(command):
            if not cmd or cmd.startswith("#"):
                continue

            # Intercept directives and update context
            new_cwd = self._handle_directives(cmd, current_cwd, current_env)
            if new_cwd != current_cwd or cmd.startswith(("export ", "set ")):
                current_cwd = new_cwd
                continue

            # Execute atomic command
            command_args, use_shell = self._prepare_command_for_platform(cmd)
            self._log_debug_pre_execution(cmd, command_args, current_cwd, use_shell)
            result = self._run_subprocess(
                command_args, use_shell, current_cwd, current_env
            )

            total_stdout.append(result["stdout"])
            total_stderr.append(result["stderr"])

            if result["return_code"] != 0:
                return {
                    "stdout": "".join(total_stdout),
                    "stderr": "".join(total_stderr),
                    "return_code": result["return_code"],
                }

        return {
            "stdout": "".join(total_stdout),
            "stderr": "".join(total_stderr),
            "return_code": 0,
        }
