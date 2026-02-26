import os
import shutil
import subprocess
import sys
from typing import Optional, Dict, List

from teddy_executor.core.domain.models.shell_output import ShellOutput
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor


class ShellAdapter(IShellExecutor):
    def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> ShellOutput:
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
            # On Windows, we prefer to pass the raw command string directly to the OS.
            # This bypasses the complex and often buggy quoting rules of list2cmdline
            # and shlex, allowing complex commands (like Python scripts) to work reliably.
            #
            # We use a dynamic router strategy:
            # 1. Extract the command name (first token).
            # 2. Check if it's an executable file using shutil.which().
            # 3. If it is a file -> Use shell=False (Clean Path to Kernel).
            # 4. If it is NOT a file -> Assume it's a shell built-in (Dirty Path to cmd.exe).

            command_args = command
            first_word = command.strip().split()[0]

            # shutil.which returns the full path if found, or None.
            executable_path = shutil.which(first_word)

            if executable_path:
                # It's a real file (e.g., python.exe, git.exe).
                # We can run it directly via the kernel.
                use_shell = False
            else:
                # It's not a file. It must be a built-in (e.g., dir, echo) or a typo.
                # We must invoke the shell to handle it.
                use_shell = True
        else:
            # On POSIX, use shell=True to support features like globbing, pipes, etc.
            # This is safe in TeDDy's context where users approve commands before execution.
            use_shell = True
            command_args = command

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

            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
            }
        except (FileNotFoundError, OSError) as e:
            if is_debug_mode:
                print("--- ShellAdapter Error ---", file=sys.stderr)
                print(f"Error: {e}", file=sys.stderr)
                print("--------------------------", file=sys.stderr)

            return {
                "stdout": "",
                "stderr": str(e),
                "return_code": getattr(e, "errno", 1),
            }
