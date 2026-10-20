"""Decompose the Windows suite wall clock by worker count and coverage.

The user reports about 30s on Windows against about 15s on macOS, which a
fixed 1.9s residual cannot explain. This probe separates process spawn plus
collection from test execution, scales the worker count, and toggles coverage
instrumentation. The serial duration report names the slowest setup, call, and
teardown phases so a per-test filesystem cost is visible.
"""

import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def run(
    label: str,
    args: list[str],
    timeout: int = 900,
    show_durations: bool = False,
) -> None:
    """Run one pytest invocation and print its wall clock and tail."""
    command = [sys.executable, "-m", "pytest", *args]
    start = time.perf_counter()
    try:
        result = subprocess.run(
            command,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"{label}: TIMEOUT after {time.perf_counter() - start:.2f}s")
        return
    elapsed = time.perf_counter() - start
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    tail = lines[-1][:140] if lines else ""
    print(f"{label}: {elapsed:.2f}s rc={result.returncode} tail={tail}")
    if result.returncode != 0:
        errors = [line.strip() for line in result.stderr.splitlines() if line.strip()]
        if errors:
            print(f"  stderr: {errors[-1][:240]}")
    if show_durations:
        in_block = False
        for line in lines:
            if "slowest durations" in line.lower():
                in_block = True
            if in_block:
                print(f"  {line[:160]}")


def main() -> None:
    print("python", sys.version.split()[0])
    print("executable", sys.executable)
    print("project root", PROJECT_ROOT)

    run("collect -n 0", ["-q", "--collect-only", "-n", "0"])
    run("collect -n auto", ["-q", "--collect-only", "-n", "auto"])
    run(
        "full -n 0 + durations",
        ["-q", "-n", "0", "--durations=20"],
        show_durations=True,
    )
    run("full -n auto", ["-q", "-n", "auto"])
    run("full -n auto --no-cov", ["-q", "-n", "auto", "--no-cov"])


if __name__ == "__main__":
    main()