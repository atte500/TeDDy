"""Measure how worker concurrency inflates the shared harness import cost.

The worker timeline shows every worker finishes its pre-test phase at nearly
the same wall moment, several seconds after the run starts. xdist starts each
worker as a fresh interpreter, and the root conftest imports the whole test
harness and application package at module level. On Windows every worker also
pays a process creation cost that a fork-based platform avoids. This probe
times a bare interpreter, a bare pytest import, and the root conftest import
serially and at six- and twelve-way concurrency, so the startup window
separates into process creation, interpreter baseline, and import contention.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

BOOTSTRAP = (
    "import sys\n"
    "sys.path.insert(0, 'src')\n"
    "sys.path.insert(0, '.')\n"
)

SCRIPTS = (
    ("bare interpreter", "pass\n"),
    ("pytest import", "import pytest\n"),
    (
        "root conftest import",
        "import tests.conftest\n"
        "print('modules', len(sys.modules))\n",
    ),
)


def run_serial(label: str, body: str) -> None:
    """Time one process that runs the given import body."""
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-c", BOOTSTRAP + body],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.perf_counter() - start
    print(f"  {label}: 1 process in {elapsed:.2f}s rc={result.returncode}")
    if result.stdout.strip():
        print("    stdout:", result.stdout.strip()[:120])
    if result.returncode != 0:
        tail = [line for line in result.stderr.splitlines() if line.strip()]
        print("    stderr:", tail[-1][:200] if tail else "")


def run_parallel(label: str, body: str, count: int) -> None:
    """Time `count` processes launched together that run the same import body."""
    start = time.perf_counter()
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", BOOTSTRAP + body],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
        )
        for _ in range(count)
    ]
    failures = 0
    for process in processes:
        _stdout, stderr = process.communicate()
        if process.returncode != 0:
            failures += 1
            if failures == 1:
                lines = [line for line in (stderr or "").splitlines() if line.strip()]
                print("    first failure:", lines[-1][:200] if lines else "")
    elapsed = time.perf_counter() - start
    print(
        f"  {label}: {count} processes in {elapsed:.2f}s "
        f"(wall), failures={failures}"
    )


def main() -> None:
    """Measure each import stage serially and under worker-level concurrency."""
    print("cpu_count", os.cpu_count())
    print("python", sys.version.split()[0])
    print("project root", PROJECT_ROOT)
    for label, body in SCRIPTS:
        print(f"\n== {label} ==")
        run_serial(label, body)
        run_parallel(label, body, 6)
        run_parallel(label, body, 12)


if __name__ == "__main__":
    main()