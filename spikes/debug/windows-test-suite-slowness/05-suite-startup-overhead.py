"""Measure pytest startup and collection cost serially and under xdist.

The loopback fix removed the per-request stall, so the remaining Windows
overhead is fixed work paid once per worker. Collection exercises spawn,
imports, conftest setup, and test discovery without running test bodies.
"""

import os
import subprocess
import sys
import time


def run(label: str, args: list[str]) -> None:
    """Run pytest with the given arguments and print its wall-clock cost."""
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - start
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    tail = lines[-1][:100] if lines else ""
    print(f"{label}: {elapsed:.2f}s rc={result.returncode} tail={tail}")
    if result.returncode != 0:
        errors = [line for line in result.stderr.splitlines() if line.strip()]
        print(f"{label} stderr: {errors[-1][:200] if errors else ''}")


def main() -> None:
    print("cpu_count", os.cpu_count())
    run("serial collect-only", ["-n", "0", "--collect-only", "-q"])
    run("xdist collect-only", ["-n", "auto", "--collect-only", "-q"])


if __name__ == "__main__":
    main()