import os
import shlex
import subprocess
import sys
from typing import Optional, Dict, List

from teddy_executor.core.domain.models import CommandResult
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor

# A list of common Windows shell built-ins.
# This list is not exhaustive but covers frequent commands.
WINDOWS_SHELL_BUILTINS = [
    "dir",
    "copy",
    "del",
    "erase",
    "ren",
    "rename",
    "mkdir",
    "rmdir",
    "echo",
    "type",
    "vol",
    "ver",
    "date",
    "time",
    "cls",
    "call",
    "set",
    "path",
    "prompt",
]


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
            if os.path.isabs(cwd):
                validated_cwd = os.path.realpath(cwd)
            else:
                validated_cwd = os.path.realpath(os.path.join(project_root, cwd))

            if not validated_cwd.startswith(project_root):
                raise ValueError(
                    f"Validation failed: `cwd` path '{cwd}' resolves to '{validated_cwd}', which is outside the project directory '{project_root}'."
                )
        else:
            validated_cwd = project_root

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        is_windows = sys.platform == "win32"
        use_shell = False
        command_args: List[str] | str = ""

        if is_windows:
            # On Windows, check if the command is a known shell built-in.
            # If so, we MUST use shell=True.
            first_word = command.strip().split()[0].lower()
            if first_word in WINDOWS_SHELL_BUILTINS:
                use_shell = True
                command_args = command
            else:
                # For executables, use shell=False for safety, but ensure
                # shlex splits in non-POSIX mode to handle backslashes correctly.
                use_shell = False
                command_args = shlex.split(command, posix=False)
        else:
            # On POSIX, the default strategy is generally safe and robust.
            use_shell = False
            command_args = shlex.split(command)

        is_debug_mode = os.getenv("TEDDY_DEBUG")
        if is_debug_mode:
            print("--- ShellAdapter Debug ---", file=sys.stderr)
            print(f"Platform: {sys.platform}", file=sys.stderr)
            print(f"Original command: {command!r}", file=sys.stderr)
            print(f"Tokenized/Command args: {command_args}", file=sys.stderr)
            print(f"CWD: {validated_cwd}", file=sys.stderr)
            print(f"Shell: {use_shell}", file=sys.stderr)
            print("--------------------------", file=sys.stderr)

        try:
            result = subprocess.run(
                command_args,
                shell=use_shell,
                capture_output=True,
                text=True,
                check=False,
                cwd=validated_cwd,
                env=merged_env,
            )

            if is_debug_mode:
                print("--- ShellAdapter Result ---", file=sys.stderr)
                print(f"Return Code: {result.returncode}", file=sys.stderr)
                print(f"STDOUT:\n{result.stdout}", file=sys.stderr)
                print(f"STDERR:\n{result.stderr}", file=sys.stderr)
                print("---------------------------", file=sys.stderr)

            return CommandResult(
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
            )
        except (FileNotFoundError, OSError) as e:
            if is_debug_mode:
                print("--- ShellAdapter Error ---", file=sys.stderr)
                print(f"Error: {e}", file=sys.stderr)
                print("--------------------------", file=sys.stderr)

            return CommandResult(
                stdout="",
                stderr=str(e),
                return_code=getattr(e, "errno", 1),
            )
