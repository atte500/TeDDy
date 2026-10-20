"""Measure the suite's parallel speedup curve with no instrumentation loaded.

The serial suite costs about 95s and the default `-n auto` run costs about
29s, a 3.2x speedup on 12 logical CPUs. Eight seconds would be ideal, and the
user reports roughly 15s on macOS for the same suite. The earlier os-wrapping
plugin is rejected because it corrupted pyfakefs state, so this probe loads no
plugin at all. A curve that rises steeply and then flattens short of ideal
points at CPU contention from oversubscribed hyperthreads. A curve that stays
near ideal and only starts from a higher serial floor points at serial test
work, which the phase decomposition already located in the test bodies.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKER_COUNTS = (1, 2, 4, 6, 8, 12)


def run(label: str, args: list[str], timeout: int = 900) -> float | None:
    """Run one pytest invocation and print its wall clock and tail."""
    start = time.perf_counter()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", *args],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"{label}: TIMEOUT after {time.perf_counter() - start:.2f}s")
        return None
    elapsed = time.perf_counter() - start
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    tail = lines[-1][:120] if lines else ""
    print(f"{label}: {elapsed:.2f}s rc={result.returncode} tail={tail}")
    if result.returncode != 0:
        errors = [line.strip() for line in result.stderr.splitlines() if line.strip()]
        if errors:
            print(f"  stderr: {errors[-1][:200]}")
    return elapsed


def main() -> None:
    """Run the suite once per worker count and print the speedup curve."""
    print("cpu_count", os.cpu_count())
    print("python", sys.version.split()[0])
    baseline = None
    for workers in WORKER_COUNTS:
        elapsed = run(f"-n {workers}", ["-q", "-n", str(workers)])
        if elapsed is None:
            continue
        if workers == 1:
            baseline = elapsed
        if baseline:
            print(f"  speedup vs serial: {baseline / elapsed:.2f}x on {workers} workers")


if __name__ == "__main__":
    main()