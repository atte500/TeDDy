"""Repeat the dispatch comparison and size the collection phase.

Probe 14 shows that every worker's first test begins at the same wall moment,
2.4-4.6s after that worker started, while probe 15 shows the harness import
costs at most 0.75s even under twelve-way contention. Collection of the full
test session inside every worker is the remaining candidate for that window.
Probe 13 also measured one sample per dispatch mode, so its four-second gain
needs a repeat before it justifies a configuration change. This probe repeats
the twelve-worker default and twelve-worker worksteal runs twice each, adds
the eight-worker worksteal control, and measures collection-only wall clock at
both widths.
"""

import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPEATS = 2

CONFIGS = (
    ("n12 load", ("-q", "-n", "12"), REPEATS),
    ("n12 worksteal", ("-q", "-n", "12", "--dist", "worksteal"), REPEATS),
    ("n8 worksteal", ("-q", "-n", "8", "--dist", "worksteal"), REPEATS),
    ("n12 collect-only", ("-q", "-n", "12", "--collect-only"), 1),
    ("n8 collect-only", ("-q", "-n", "8", "--collect-only"), 1),
)


def run_once(args: tuple[str, ...], timeout: int = 900) -> tuple[float, int, str]:
    """Run one pytest invocation and return its wall clock, code, and tail."""
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    elapsed = time.perf_counter() - start
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    tail = lines[-1][:120] if lines else ""
    if result.returncode != 0:
        errors = [line.strip() for line in result.stderr.splitlines() if line.strip()]
        if errors:
            print(f"  stderr: {errors[-1][:200]}")
    return elapsed, result.returncode, tail


def main() -> None:
    """Run every configuration and print per-run and per-configuration walls."""
    print("cpu_count", os.cpu_count())
    print("python", sys.version.split()[0])
    print("repeats per configuration", REPEATS)
    means: dict[str, float] = {}
    for label, args, repeats in CONFIGS:
        samples: list[float] = []
        for index in range(repeats):
            elapsed, code, tail = run_once(args)
            samples.append(elapsed)
            print(f"{label} #{index + 1}: {elapsed:.2f}s rc={code} tail={tail}")
        means[label] = statistics.fmean(samples)
        print(f"{label}: mean {means[label]:.2f}s over {repeats} run(s)")

    baseline = means.get("n12 load")
    if baseline is None:
        return
    print()
    for label, mean in means.items():
        if label == "n12 load":
            continue
        print(f"  {label} vs n12 load: {baseline - mean:+.2f}s")


if __name__ == "__main__":
    main()