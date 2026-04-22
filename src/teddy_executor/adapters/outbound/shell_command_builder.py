import shutil
import sys
from typing import List, Union


class ShellCommandBuilder:
    """
    Handles OS-specific command preparation, wrapping, and script generation.
    """

    def __init__(self, platform: str = sys.platform):
        self._platform = platform

    def prepare(self, command: str) -> tuple[Union[str, List[str]], bool]:
        """Determines command arguments and shell usage based on the platform."""
        command = command.strip()
        is_multiline = "\n" in command

        # Check for shell operators to enable granular reporting for single-line chains.
        ops = (
            ["&&", "||", ";", "|"]
            if self._platform != "win32"
            else ["&&", "||", "&", "|"]
        )
        has_chaining = any(op in command for op in ops)
        is_complex = is_multiline or has_chaining

        if self._platform == "win32":
            return self._prepare_windows(command, is_complex)

        return self._prepare_posix(command, is_complex, is_multiline)

    def _prepare_windows(self, command: str, is_complex: bool) -> tuple[str, bool]:
        """Prepares commands for Windows cmd.exe."""
        # For Windows, we wrap complex commands if they don't look like
        # a single multiline script (e.g., using triple quotes).
        is_likely_single_script = "'''" in command or '"""' in command
        if is_complex and not is_likely_single_script:
            lines = [line.strip() for line in command.split("\n") if line.strip()]
            wrapped_parts = []
            for line in lines:
                safe_line = (
                    line.replace('"', "'")
                    .replace("^", "^^")
                    .replace("(", "^(")
                    .replace(")", "^)")
                    .replace("&", "^&")
                    .replace("|", "^|")
                    .replace(">", "^>")
                    .replace("<", "^<")
                )
                prefix = "cmd /c" if line.strip().lower().startswith("exit") else "call"
                cmd_part = f'"{line}"' if prefix == "cmd /c" else line

                wrapped_parts.append(
                    f'({prefix} {cmd_part} || cmd /c "echo FAILED_COMMAND: {safe_line} >&2 & exit 1")'
                )
            wrapped = " && ".join(wrapped_parts)
            return wrapped, True

        first_word = command.split()[0]
        if shutil.which(first_word):
            return command, False  # It's a file, run directly.
        return command, True  # It's a shell built-in.

    def _prepare_posix(
        self, command: str, is_complex: bool, is_multiline: bool
    ) -> tuple[Union[str, List[str]], bool]:
        """Prepares commands for POSIX systems (prefers bash for complex commands)."""
        if is_complex and shutil.which("bash"):
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
