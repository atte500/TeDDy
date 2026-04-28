import os
import subprocess  # nosec
import sys
from typing import Optional, Dict, List, Any

from teddy_executor.core.domain.models.shell_output import ShellOutput
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor
from teddy_executor.adapters.outbound.shell_command_builder import ShellCommandBuilder
from teddy_executor.core.utils.string import truncate_lines

import re


class ShellAdapter(IShellExecutor):
    TIMEOUT_EXIT_CODE = 124

    def __init__(
        self,
        command_builder: ShellCommandBuilder = None,  # type: ignore
        max_execute_lines: int = 100,
    ):
        self._command_builder = command_builder or ShellCommandBuilder()
        self.max_execute_lines = max_execute_lines

    def _sanitize_output(self, text: str) -> str:
        """Strips ALL ANSI escape sequences to prevent playback corruption and garbled reports."""
        if not text:
            return text
        # Remove Operating System Commands (like window title changes)
        text = re.sub(r"\x1b\][^\x07\x1b]*?(?:\x07|\x1b\\)", "", text)
        # Remove all CSI escape sequences (including colors, cursor moves, alt-screens)
        text = re.sub(r"\x1b\[[0-9;?><\$]*[a-zA-Z]", "", text)
        return text

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

    def _restore_terminal_state(self):
        """Hard-resets terminal state to clear corruption from killed TUIs."""
        if "PYTEST_CURRENT_TEST" in os.environ:
            return  # Prevent terminal corruption during test suite execution

        reset_seq = "\x1b[?1000l\x1b[?1003l\x1b[?1049l\x1b[?25h"
        # 1. Attempt to write directly to the controlling terminal (bypasses pipes)
        try:
            with open("/dev/tty", "w") as tty:
                tty.write(reset_seq)
                tty.flush()
        except OSError:
            pass

        # 2. Fallback to stdout/stderr if /dev/tty is unavailable but they are TTYs
        if sys.stdout.isatty():
            sys.stdout.write(reset_seq)
            sys.stdout.flush()
        elif sys.stderr.isatty():
            sys.stderr.write(reset_seq)
            sys.stderr.flush()

    def _prepare_subprocess_kwargs(
        self, use_shell: bool, cwd: str, env: Dict[str, str]
    ) -> Dict[str, Any]:
        """Prepares the keyword arguments for subprocess.Popen."""
        kwargs: Dict[str, Any] = {
            "shell": use_shell,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "cwd": cwd,
            "env": env,
        }
        if sys.platform != "win32":
            import signal

            # ISOLATION: Severing stdin from the TTY is required to prevent SIGTTIN
            # suspension when running in a new process group.
            kwargs["stdin"] = subprocess.DEVNULL

            def preexec_fn():
                os.setpgrp()
                # Prevent OS from suspending background process group when querying TTY
                signal.signal(signal.SIGTTOU, signal.SIG_IGN)
                signal.signal(signal.SIGTTIN, signal.SIG_IGN)

            kwargs["preexec_fn"] = preexec_fn
        return kwargs

    def _handle_timeout(self, process: subprocess.Popen, timeout: float) -> ShellOutput:
        """Handles a subprocess timeout by terminating the process and gathering output."""
        if sys.platform != "win32":
            import signal

            try:
                # Jidoka/Poka-Yoke: Anti-Suicide Guard.
                if not isinstance(process.pid, int) or process.pid <= 1:
                    process.kill()
                else:
                    os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
        else:
            process.kill()

        try:
            # Give the OS a moment to close pipes naturally after SIGKILL.
            stdout, stderr = process.communicate(timeout=0.5)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""

        self._log_debug_error(Exception(f"TimeoutExpired: {timeout} seconds"))
        warning = f"[ERROR: Command timed out after {timeout} seconds]"
        return {
            "stdout": f"{warning}\n{self._sanitize_output(stdout)}".strip()
            if stdout
            else warning,
            "stderr": self._sanitize_output(stderr) or "",
            "return_code": self.TIMEOUT_EXIT_CODE,
        }

    def _process_execution_results(
        self, stdout: str, stderr: str, return_code: int
    ) -> ShellOutput:
        """Processes the raw execution results into a structured ShellOutput."""
        sanitized_stdout = self._sanitize_output(stdout)
        hint = "[Output truncated. Use 'command > file.txt' or 'grep' to filter results if needed.]"

        truncated_stdout = truncate_lines(
            sanitized_stdout,
            max_lines=self.max_execute_lines,
            direction="tail",
            hint=hint,
        )

        output: ShellOutput = {
            "stdout": truncated_stdout,
            "stderr": self._sanitize_output(stderr),
            "return_code": return_code,
        }

        marker = "FAILED_COMMAND: "
        if marker in stderr:
            for line in stderr.splitlines():
                if marker in line:
                    output["failed_command"] = line.split(marker)[1].strip()
                    break
        return output

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

            kwargs = self._prepare_subprocess_kwargs(use_shell, cwd, env)
            process = subprocess.Popen(command_args, **kwargs)  # nosec

            try:
                # Type cast is required because Mypy cannot infer str types when
                # text=True is passed via **kwargs.
                from typing import cast

                comm_res = process.communicate(timeout=timeout)
                stdout, stderr = cast(tuple[str, str], comm_res)
            except subprocess.TimeoutExpired:
                return self._handle_timeout(process, timeout or 0)

            self._log_debug_result(
                subprocess.CompletedProcess(
                    args=command_args,
                    returncode=process.returncode,
                    stdout=stdout,
                    stderr=stderr,
                )
            )

            return self._process_execution_results(stdout, stderr, process.returncode)
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

        command_args, use_shell = self._command_builder.prepare(command)
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
