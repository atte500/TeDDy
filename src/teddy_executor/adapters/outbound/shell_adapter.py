import os
import shutil
import subprocess  # nosec
import sys
from typing import Optional, Dict, List

from teddy_executor.core.domain.models.shell_output import ShellOutput
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor


class ShellAdapter(IShellExecutor):
    TIMEOUT_EXIT_CODE = 124

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
        command = command.strip()
        is_multiline = "\n" in command
        # Check for shell operators to enable granular reporting for single-line chains.
        # Note: ';' is not a command separator on Windows cmd.exe.
        ops = (
            ["&&", "||", ";", "|"]
            if sys.platform != "win32"
            else ["&&", "||", "&", "|"]
        )
        has_chaining = any(op in command for op in ops)
        is_complex = is_multiline or has_chaining

        if sys.platform == "win32":
            # For Windows, we wrap complex commands if they don't look like
            # a single multiline script (e.g., using triple quotes).
            is_likely_single_script = "'''" in command or '"""' in command
            if is_complex and not is_likely_single_script:
                # Wrap complex commands to fail-fast on Windows.
                lines = [line.strip() for line in command.split("\n") if line.strip()]
                wrapped_parts = []
                for line in lines:
                    # Escape special characters that break cmd.exe parentheses or redirect output.
                    # THE FIX: Replace double quotes to prevent breaking the outer "..."
                    safe_line = (
                        line.replace('"', "'")
                        .replace("(", "^(")
                        .replace(")", "^)")
                        .replace("&", "^&")
                        .replace("|", "^|")
                        .replace(">", "^>")
                        .replace("<", "^<")
                    )
                    wrapped_parts.append(
                        f'({line} || cmd /c "echo FAILED_COMMAND: {safe_line} >&2 & exit 1")'
                    )
                wrapped = " && ".join(wrapped_parts)
                return wrapped, True

            first_word = command.split()[0]
            if shutil.which(first_word):
                return command, False  # It's a file, run directly.
            return command, True  # It's a shell built-in.

        # On POSIX
        if is_complex and shutil.which("bash"):
            # Use a high-precision diagnostic script that tracks the specific command.
            # We use a DEBUG trap to capture the command before it runs and an EXIT trap
            # to report it. We use a function for the EXIT trap because the DEBUG trap
            # does not fire for commands executed inside a trap handler function,
            # ensuring TEDDY_LAST_CMD remains untainted by our cleanup logic.
            script = (
                "__teddy_report() { "
                "RET=$?; "
                "if [ $RET -ne 0 ]; then "
                'echo "FAILED_COMMAND: $TEDDY_LAST_CMD" >&2; '
                "fi; "
                "exit $RET; "
                "}\n"
                "trap 'TEDDY_LAST_CMD=$BASH_COMMAND' DEBUG\n"
                "trap '__teddy_report' EXIT\n"
                "set -e\n"
                f"{command}"
            )
            return ["bash", "-c", script], False

        # Fallback for simple single-line or when bash is missing
        prefix = "set -e; " if is_multiline else ""
        return f"{prefix}{command}", True

    def _log_debug_pre_execution(
        self, command: str, command_args: str | List[str], cwd: str, use_shell: bool
    ):
        if os.getenv("TEDDY_DEBUG"):  # pragma: no cover
            print("--- ShellAdapter Debug ---", file=sys.stderr)
            print(f"Platform: {sys.platform}", file=sys.stderr)
            print(f"Original command: {command!r}", file=sys.stderr)
            print(f"Tokenized/Command args: {command_args}", file=sys.stderr)
            print(f"CWD: {cwd}", file=sys.stderr)
            print(f"Shell: {use_shell}", file=sys.stderr)
            print("--------------------------", file=sys.stderr)

    def _log_debug_result(self, result: subprocess.CompletedProcess):
        if os.getenv("TEDDY_DEBUG"):  # pragma: no cover
            print("--- ShellAdapter Result ---", file=sys.stderr)
            print(f"Return Code: {result.returncode}", file=sys.stderr)
            print(f"STDOUT:\n{result.stdout}", file=sys.stderr)
            print(f"STDERR:\n{result.stderr}", file=sys.stderr)
            print("---------------------------", file=sys.stderr)

    def _log_debug_error(self, error: Exception):
        if os.getenv("TEDDY_DEBUG"):  # pragma: no cover
            print("--- ShellAdapter Error ---", file=sys.stderr)
            print(f"Error: {error}", file=sys.stderr)
            print("--------------------------", file=sys.stderr)

    def _run_subprocess(  # noqa: PLR0913
        self,
        command_args: str | List[str],
        use_shell: bool,
        cwd: str,
        env: Dict[str, str],
        timeout: Optional[float] = None,
        background: bool = False,
    ) -> ShellOutput:
        """Executes the command in a subprocess and handles errors."""
        try:
            if background:
                process = subprocess.Popen(  # nosec B602
                    command_args,
                    shell=use_shell,
                    cwd=cwd,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return {
                    "stdout": f"[SUCCESS: Background process started with PID {process.pid}]",
                    "stderr": "",
                    "return_code": 0,
                }

            result = subprocess.run(  # nosec B602
                command_args,
                shell=use_shell,
                capture_output=True,
                text=True,
                check=False,
                cwd=cwd,
                env=env,
                timeout=timeout,
            )
            self._log_debug_result(result)

            output: ShellOutput = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
            }

            # Extract granular failure info if present in stderr
            marker = "FAILED_COMMAND: "
            if marker in result.stderr:
                for line in result.stderr.splitlines():
                    if marker in line:
                        output["failed_command"] = line.split(marker)[1].strip()
                        break

            return output
        except subprocess.TimeoutExpired as e:
            self._log_debug_error(e)
            # Decode partial output. While often bytes even with text=True,
            # we handle both for robustness across Python versions.
            stdout = (
                e.stdout.decode("utf-8", errors="replace")
                if isinstance(e.stdout, bytes)
                else (e.stdout or "")
            )
            stderr = (
                e.stderr.decode("utf-8", errors="replace")
                if isinstance(e.stderr, bytes)
                else (e.stderr or "")
            )

            warning = f"[ERROR: Command timed out after {e.timeout} seconds]"
            return {
                "stdout": f"{warning}\n{stdout}".strip() if stdout else warning,
                "stderr": stderr,
                "return_code": self.TIMEOUT_EXIT_CODE,
            }
        except (FileNotFoundError, OSError) as e:
            self._log_debug_error(e)
            return {
                "stdout": "",
                "stderr": str(e),
                "return_code": getattr(e, "errno", 1),
            }

    # jscpd:ignore-start
    def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        background: bool = False,
    ) -> ShellOutput:
        # jscpd:ignore-end
        """Executes a command via subprocess, returning ShellOutput."""
        current_cwd = self._validate_cwd(cwd)
        current_env = os.environ.copy()
        if env:
            current_env.update(env)

        # Directives (cd, export) are now pre-processed by the parser.
        # The adapter's responsibility is to execute a single, final command.

        command_args, use_shell = self._prepare_command_for_platform(command)
        self._log_debug_pre_execution(command, command_args, current_cwd, use_shell)
        result = self._run_subprocess(
            command_args,
            use_shell,
            current_cwd,
            current_env,
            timeout=timeout,
            background=background,
        )

        return result
