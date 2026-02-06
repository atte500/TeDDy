import os
import shlex
import subprocess
import sys
from typing import Callable, List, Dict, Any

# This import is Level 3 (Specific Library)
from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter

# --- Test Commands ---
# A set of commands designed to probe different failure modes.
COMMANDS_TO_TEST = {
    "simple_executable": f"{sys.executable} -c \"print('simple_executable_works')\"",
    "multiline_arg": f"{sys.executable} -c \"print('''line one\nline two''')\"",
    "posix_shell_builtin": "echo 'posix_builtin_works'",
    "windows_shell_builtin": "dir",
}

# --- Execution Strategies (The things we are testing) ---

def run_os_system(command: str) -> subprocess.CompletedProcess:
    """Level 1: Raw OS/Shell interaction."""
    try:
        # os.system doesn't capture output, so we can't verify stdout
        # We only care about the return code. 0 is success.
        ret_code = os.system(command)
        return subprocess.CompletedProcess(args=command, returncode=ret_code, stdout=b"", stderr=b"")
    except Exception:
        return subprocess.CompletedProcess(args=command, returncode=-1, stdout=b"", stderr=b"")

def run_subprocess_shell_true(command: str) -> subprocess.CompletedProcess:
    """Level 2: Standard Library with shell=True."""
    return subprocess.run(command, shell=True, capture_output=True, text=True)

def run_subprocess_shell_false(command: str) -> subprocess.CompletedProcess:
    """Level 2: Standard Library with shell=False and shlex.split."""
    return subprocess.run(shlex.split(command), shell=False, capture_output=True, text=True)

def run_shell_adapter(command: str) -> subprocess.CompletedProcess:
    """Level 3: Project's Specific Library."""
    adapter = ShellAdapter()
    result = adapter.execute(command)
    # Adapt CommandResult to CompletedProcess for consistent interface
    return subprocess.CompletedProcess(
        args=command,
        returncode=result.return_code,
        stdout=result.stdout,
        stderr=result.stderr,
    )

STRATEGIES: Dict[str, Callable[[str], Any]] = {
    "os.system": run_os_system,
    "subprocess(shell=True)": run_subprocess_shell_true,
    "subprocess(shell=False)": run_subprocess_shell_false,
    "ShellAdapter": run_shell_adapter,
}

# --- Main Oracle Logic ---

def consult_oracle():
    """Run all commands against all strategies and print a verdict matrix."""
    print(f"--- Triangulation Oracle ---")
    print(f"Platform: {sys.platform}")
    print("-" * 28)

    results_matrix: Dict[str, Dict[str, str]] = {}

    for cmd_name, command in COMMANDS_TO_TEST.items():
        results_matrix[cmd_name] = {}
        for strategy_name, strategy_func in STRATEGIES.items():
            try:
                result = strategy_func(command)
                # For os.system, we only check the return code.
                if strategy_name == "os.system":
                    verdict = "PASS" if result.returncode == 0 else "FAIL"
                else:
                    verdict = "PASS" if result.returncode == 0 and not result.stderr else "FAIL"
            except Exception as e:
                verdict = f"ERROR: {type(e).__name__}"

            results_matrix[cmd_name][strategy_name] = verdict

    # --- Print Verdict Matrix ---
    header = f"{'Command':<25} | {'os.system':<12} | {'subprocess(shell=True)':<24} | {'subprocess(shell=False)':<25} | {'ShellAdapter':<15}"
    print(header)
    print("=" * len(header))

    for cmd_name, strategy_results in results_matrix.items():
        row = (
            f"{cmd_name:<25} | "
            f"{strategy_results.get('os.system', 'N/A'):<12} | "
            f"{strategy_results.get('subprocess(shell=True)', 'N/A'):<24} | "
            f"{strategy_results.get('subprocess(shell=False)', 'N/A'):<25} | "
            f"{strategy_results.get('ShellAdapter', 'N/A'):<15}"
        )
        print(row)

    # --- Final Verdict based on a key heuristic ---
    # The core problem is executing shell built-ins.
    # The PREMISE is that a single strategy works for all commands.
    # We test this by seeing if the `ShellAdapter` (the current implementation)
    # can successfully run both a simple executable AND a platform-specific shell built-in.

    is_windows = sys.platform == "win32"
    native_builtin_cmd = "windows_shell_builtin" if is_windows else "posix_shell_builtin"

    adapter_simple_ok = results_matrix["simple_executable"]["ShellAdapter"] == "PASS"
    adapter_builtin_ok = results_matrix[native_builtin_cmd]["ShellAdapter"] == "PASS"

    if adapter_simple_ok and adapter_builtin_ok:
        print("\n--- ORACLE VERDICT: PREMISE VALIDATED ---")
        print("The ShellAdapter successfully handled both executables and shell built-ins.")
    else:
        print("\n--- ORACLE VERDICT: PREMISE FLAWED ---")
        print("The current ShellAdapter strategy fails to handle all command types.")
        if not adapter_simple_ok:
            print("Reason: It failed on a simple executable.")
        if not adapter_builtin_ok:
            print("Reason: It failed on a native shell built-in.")


if __name__ == "__main__":
    consult_oracle()
