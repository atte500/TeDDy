"""Attribute the parallel suite wall clock and the operating-system volume.

Probe 06 measured 94.84s serial and 29.41s under `-n auto`. Probe 07 placed
91.48s of the serial run in the setup, call, and teardown phases, with only
1.73s in process creation and 0.31s in workspace churn. This probe answers two
questions. First, where the parallel wall clock goes: it records when each
xdist worker starts, when it finishes, and what it executed. Second, how much
time the suite spends inside operating-system calls: the plugin times every
file open, stat, directory scan, spawn, and sleep, so the volume converts to
seconds on this host instead of remaining a guess.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = Path(__file__).resolve().parent
REPORT_DIR = Path(tempfile.gettempdir()) / "teddy-suite-os-probe"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def bench(label, function, iterations):
    """Print the wall clock and per-call cost of a repeated operation."""
    start = time.perf_counter()
    for _ in range(iterations):
        function()
    elapsed = time.perf_counter() - start
    per_call = elapsed / iterations
    print(
        f"bench {label}: {iterations} calls, {elapsed:.3f}s total, "
        f"{per_call * 1000:.4f}ms each"
    )


def bench_primitives():
    """Measure the raw per-call cost of the primitives the suite exercises."""
    root = Path(tempfile.mkdtemp(prefix="teddy-suite-bench-"))
    sequence = iter(range(10**9))

    def file_cycle():
        path = root / f"file_{next(sequence)}.txt"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("x" * 1024)
        path.stat()
        path.unlink()

    def directory_cycle():
        path = root / f"dir_{next(sequence)}"
        path.mkdir()
        path.rmdir()

    def resolve_cycle():
        (root / "a" / "b").resolve()

    scan_root = root / "scan"
    scan_root.mkdir()
    for index in range(200):
        (scan_root / f"file_{index}.txt").touch()

    def scan_cycle():
        with os.scandir(scan_root) as iterator:
            for _entry in iterator:
                pass

    def thread_cycle():
        thread = threading.Thread(target=lambda: None)
        thread.start()
        thread.join()

    bench("create+write1KB+stat+delete", file_cycle, 200)
    bench("mkdir+rmdir", directory_cycle, 200)
    bench("Path.resolve deep path", resolve_cycle, 500)
    bench("os.getcwd", os.getcwd, 500)
    bench("os.scandir over 200 files", scan_cycle, 100)
    bench("thread start+join", thread_cycle, 100)
    try:
        bench(
            "spawn cmd /c echo",
            lambda: subprocess.run(["cmd", "/c", "echo", "x"], capture_output=True),
            5,
        )
    except (OSError, ValueError) as error:
        print("bench spawn cmd unavailable:", error)
    bench(
        "spawn python -c pass",
        lambda: subprocess.run([sys.executable, "-c", "pass"], capture_output=True),
        3,
    )
    shutil.rmtree(root, ignore_errors=True)


def summarize(label, run_start, run_end):
    """Print the worker timeline and the aggregated syscall accounting."""
    reports = []
    for path in sorted(REPORT_DIR.glob("report-*.json")):
        try:
            reports.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    if not reports:
        print(f"{label}: no reports were written")
        return
    workers = sorted(
        [report for report in reports if report["is_worker"]],
        key=lambda report: report["session_start_wall"],
    )
    controllers = [report for report in reports if not report["is_worker"]]
    print(
        f"{label}: wall {run_end - run_start:.2f}s, workers {len(workers)}, "
        f"controllers {len(controllers)}"
    )
    for report in workers:
        start_offset = report["session_start_wall"] - run_start
        span = report["session_end_wall"] - report["session_start_wall"]
        last_offset = (
            report["last_report_wall"] or report["session_end_wall"]
        ) - run_start
        call_phase = report["phase"]["call"]["seconds"]
        setup_phase = report["phase"]["setup"]["seconds"]
        teardown_phase = report["phase"]["teardown"]["seconds"]
        ops = sum(report["ops_total"].values())
        print(
            f"  pid={report['pid']} start=+{start_offset:.2f}s span={span:.2f}s "
            f"last_report=+{last_offset:.2f}s tests={report['call_reports']} "
            f"setup={setup_phase:.2f}s call={call_phase:.2f}s "
            f"teardown={teardown_phase:.2f}s ops={ops} "
            f"sleep={report['sleep_seconds']:.2f}s"
        )
    total_ops = Counter()
    total_op_seconds = Counter()
    total_setup = total_call = total_teardown = total_sleep = 0.0
    heaviest = {}
    slowest = {}
    for report in workers:
        total_setup += report["phase"]["setup"]["seconds"]
        total_call += report["phase"]["call"]["seconds"]
        total_teardown += report["phase"]["teardown"]["seconds"]
        total_sleep += report["sleep_seconds"]
        total_ops.update(report["ops_total"])
        total_op_seconds.update(report["op_seconds"])
        for item in report["op_heavy"]:
            entry = heaviest.setdefault(
                item["nodeid"], {"ops": 0, "seconds": item["seconds"]}
            )
            entry["ops"] += item["ops"]
        for item in report["slow_calls"]:
            slowest[item["nodeid"]] = max(
                slowest.get(item["nodeid"], 0.0), item["seconds"]
            )
    print(
        f"  worker totals: setup {total_setup:.2f}s call {total_call:.2f}s "
        f"teardown {total_teardown:.2f}s sleep {total_sleep:.2f}s"
    )
    print("  ops by volume with measured seconds inside the call:")
    for operation, count in total_ops.most_common(12):
        print(
            f"    {operation}: calls={count} "
            f"inside={total_op_seconds[operation]:.2f}s"
        )
    print("  heaviest tests by operating-system calls:")
    for nodeid, entry in sorted(
        heaviest.items(), key=lambda item: item[1]["ops"], reverse=True
    )[:10]:
        per_op = (entry["seconds"] / entry["ops"] * 1000) if entry["ops"] else 0.0
        print(
            f"    {entry['ops']} ops, call {entry['seconds']:.2f}s "
            f"({per_op:.3f}ms per op) {nodeid}"
        )
    print("  slowest call phases:")
    for nodeid, seconds in sorted(
        slowest.items(), key=lambda item: item[1], reverse=True
    )[:10]:
        print(f"    {seconds:.3f}s {nodeid}")


def run_suite(label, worker_args, timeout=900):
    """Run one instrumented suite pass and summarize its worker reports."""
    for path in REPORT_DIR.glob("report-*.json"):
        path.unlink()
    env = dict(os.environ)
    env["PYTEST_PLUGINS"] = "pytest_suite_os_probe"
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{PLUGIN_DIR}{os.pathsep}{existing}" if existing else str(PLUGIN_DIR)
    )
    start = time.time()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *worker_args, "-q"],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    end = time.time()
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    tail = lines[-1][:140] if lines else ""
    print(f"\n=== {label}: wall {end - start:.2f}s rc={result.returncode} {tail}")
    if result.returncode != 0:
        for line in result.stderr.splitlines()[-6:]:
            print("stderr:", line[:240])
    summarize(label, start, end)


def main():
    """Benchmark the primitives, then run the suite at two worker counts."""
    print("cpu_count", os.cpu_count())
    print("python", sys.version.split()[0])
    bench_primitives()
    run_suite("auto", ["-n", "auto"])
    run_suite("n6", ["-n", "6"])


if __name__ == "__main__":
    main()