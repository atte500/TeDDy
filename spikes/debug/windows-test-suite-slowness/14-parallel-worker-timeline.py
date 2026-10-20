"""Reconstruct the parallel suite timeline from per-test report windows.

Probe 13 showed chunked dispatch saves about four seconds, and the worker
curve is reproduced only when a per-worker term near 1.4s is admitted. That
shape appears when the controller starts workers one after another, so each
worker pays its import and handshake cost while earlier workers already run.
This probe records every report's offset inside each process, then
reconstructs worker start offsets, busy time, idle capacity, and the tail
after the last test for two configurations.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = Path(__file__).resolve().parent
REPORT_DIR = Path(tempfile.gettempdir()) / "teddy-parallel-timeline"

RUNS = (
    ("n12 load", ("-q", "-n", "12")),
    ("n8 worksteal", ("-q", "-n", "8", "--dist", "worksteal")),
)


def load_reports() -> list[dict]:
    """Read every timeline report the plugin wrote."""
    reports = []
    for path in sorted(REPORT_DIR.glob("timeline-*.json")):
        try:
            reports.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return reports


def summarize(label: str, wall: float) -> None:
    """Print the worker timeline, the utilisation, and the post-test tail."""
    reports = load_reports()
    if not reports:
        print(f"{label}: no timeline reports were written")
        return
    origin = min(report["session_start_wall"] for report in reports)
    workers = sorted(
        [report for report in reports if report["is_worker"]],
        key=lambda report: report["session_start_wall"],
    )
    print(
        f"\n{label}: wall {wall:.2f}s, workers {len(workers)}, "
        f"reports {len(reports)}"
    )
    print(
        f"  {'idx':>3} {'start':>7} {'first':>7} {'gap':>6} {'last':>7} "
        f"{'busy':>6} {'util':>5} {'tests':>6}"
    )
    total_busy = 0.0
    makespan = 0.0
    starts: list[float] = []
    for index, report in enumerate(workers, start=1):
        windows = report["reports"]
        if not windows:
            continue
        # report.start is an absolute POSIX timestamp, so every offset must
        # subtract the session origin instead of adding the worker start.
        start_offset = report["session_start_wall"] - origin
        first = min(start for _when, start, _duration in windows) - origin
        last = max(start + duration for _when, start, duration in windows) - origin
        busy = sum(duration for _when, _start, duration in windows)
        call_count = sum(1 for when, _start, _duration in windows if when == "call")
        span = last - first
        utilisation = busy / span if span else 0.0
        starts.append(start_offset)
        total_busy += busy
        makespan = max(makespan, last)
        print(
            f"  {index:3d} {start_offset:7.2f} {first:7.2f} {first - start_offset:6.2f} "
            f"{last:7.2f} {busy:6.2f} {utilisation:5.0%} {call_count:6d}"
        )
    if not starts:
        return
    deltas = [
        round(later - earlier, 2) for earlier, later in zip(starts, starts[1:])
    ]
    print(f"  worker start deltas: {deltas}")
    print(
        f"  sequential work {total_busy:.2f}s across {len(workers)} workers, "
        f"makespan {makespan:.2f}s"
    )
    if makespan > 0:
        capacity = makespan * len(workers)
        print(
            f"  aggregate utilisation {total_busy / capacity:.0%} of "
            f"worker-seconds, idle {capacity - total_busy:.2f}s"
        )
    print(
        f"  wall minus makespan: {wall - makespan:.2f}s "
        f"(includes spawn before the session origin)"
    )


def run_suite(label: str, args: tuple[str, ...], timeout: int = 900) -> None:
    """Run one suite pass with the timeline plugin and summarize it."""
    for path in REPORT_DIR.glob("timeline-*.json"):
        path.unlink()
    env = dict(os.environ)
    env["PYTEST_PLUGINS"] = "pytest_parallel_timeline_probe"
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{PLUGIN_DIR}{os.pathsep}{existing}" if existing else str(PLUGIN_DIR)
    )
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    wall = time.perf_counter() - start
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    tail = lines[-1][:140] if lines else ""
    print(f"\n=== {label}: wall {wall:.2f}s rc={result.returncode} tail={tail}")
    if result.returncode != 0:
        for line in result.stderr.splitlines()[-6:]:
            print("stderr:", line[:240])
    summarize(label, wall)


def main() -> None:
    """Run each configuration and print its reconstructed timeline."""
    print("cpu_count", os.cpu_count())
    print("python", sys.version.split()[0])
    print("project root", PROJECT_ROOT)
    for label, args in RUNS:
        run_suite(label, args)


if __name__ == "__main__":
    main()