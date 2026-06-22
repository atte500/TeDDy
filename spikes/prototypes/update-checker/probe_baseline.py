"""
Empirical Probe: Update Checker Baseline
=========================================
Documents current system behavior for features targeted by Slice 00-02.
Captures raw output from the real system — no assertions, no mocking.
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PYTHON = sys.executable


def run_teddy(args: list[str]) -> dict:
    """Run a teddy command and return exit code, stdout, stderr."""
    result = subprocess.run(
        [PYTHON, "-m", "teddy_executor", *args],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=15
    )
    return {
        "args": args,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def probe_version_flag() -> dict:
    """Probe: teddy --version"""
    return run_teddy(["--version"])


def probe_version_command() -> dict:
    """Probe: teddy version"""
    return run_teddy(["version"])


def probe_update_command() -> dict:
    """Probe: teddy update (should fail — command not implemented)"""
    return run_teddy(["update"])


def probe_config_auto_update() -> dict:
    """Probe: Check if auto_update key exists in config.yaml baseline."""
    config_path = PROJECT_ROOT / "src" / "teddy_executor" / "resources" / "config" / "config.yaml"
    content = config_path.read_text(encoding="utf-8")
    return {
        "file": str(config_path),
        "has_auto_update": "auto_update" in content,
        "content_snippet_before_llm": content.split("llm:")[0] if "llm:" in content else content,
    }


def probe_prewarming_location() -> dict:
    """Probe: Confirm pre-warming is inline in __main__.py init command."""
    main_py = PROJECT_ROOT / "src" / "teddy_executor" / "__main__.py"
    lines = main_py.read_text(encoding="utf-8").splitlines()
    # Find the init command function
    init_start = None
    prewarm_lines = []
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("def init()"):
            init_start = i
        if init_start and "import litellm" in line:
            # Capture the pre-warming block
            for j in range(i - 1, min(i + 10, len(lines))):
                prewarm_lines.append((j + 1, lines[j]))
            break
    return {
        "prewarming_in_main_init": init_start is not None,
        "init_function_start_line": init_start,
        "prewarm_block_lines": prewarm_lines,
    }


def main():
    print("=" * 72)
    print("EMPIRICAL PROBE: UPDATE CHECKER BASELINE")
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Python: {PYTHON}")
    print("=" * 72)

    # 1. --version flag
    print("\n--- [1] PROBE: teddy --version ---")
    result = probe_version_flag()
    print(f"  Exit code: {result['exit_code']}")
    print(f"  stdout: {result['stdout'].strip()!r}")
    print(f"  stderr: {result['stderr'].strip()!r}")

    # 2. version command
    print("\n--- [2] PROBE: teddy version ---")
    result = probe_version_command()
    print(f"  Exit code: {result['exit_code']}")
    print(f"  stdout: {result['stdout'].strip()!r}")
    print(f"  stderr: {result['stderr'].strip()!r}")

    # 3. update command (expect failure)
    print("\n--- [3] PROBE: teddy update (expect failure) ---")
    result = probe_update_command()
    print(f"  Exit code: {result['exit_code']}")
    print(f"  stdout: {result['stdout'].strip()!r}")
    print(f"  stderr: {result['stderr'].strip()!r}")

    # 4. Config auto_update key
    print("\n--- [4] PROBE: config.yaml auto_update key ---")
    result = probe_config_auto_update()
    print(f"  File: {result['file']}")
    print(f"  Has 'auto_update': {result['has_auto_update']}")

    # 5. Pre-warming location
    print("\n--- [5] PROBE: Pre-warming code location ---")
    result = probe_prewarming_location()
    print(f"  Pre-warming in __main__.py init(): {result['prewarming_in_main_init']}")
    print(f"  Init function starts at line: {result['init_function_start_line']}")
    print("  Prewarm block:")
    for lineno, line in result.get("prewarm_block_lines", []):
        print(f"    L{lineno}: {line}")

    print("\n" + "=" * 72)
    print("PROBE COMPLETE — Raw baseline captured.")
    print("=" * 72)


if __name__ == "__main__":
    main()