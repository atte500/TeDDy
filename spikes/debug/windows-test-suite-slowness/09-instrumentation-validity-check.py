"""Test whether the syscall-timing plugin can measure the suite safely.

The parallel attribution run reported 29 failures under `-n auto` and 28 under
`-n 6`, against a green 1,839 baseline, and its worker timelines contradicted
each other. A measurement that changes the suite cannot explain the suite's
wall clock. This probe reruns the same plugin serially with the per-test
timeout disabled, which removes process scheduling and the five-second
guardrail from the picture. A clean run proves the wrapper only pushed slow
tests past the timeout. A failing run with real tracebacks names the
mechanism, most likely a conflict between the wrapped os attributes and the
pyfakefs patcher that the suite already guards against.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = Path(__file__).resolve().parent
REPORT_DIR = Path(tempfile.gettempdir()) / "teddy-suite-os-probe"


def run_serial(label: str, extra_args: list[str], timeout: int = 600) -> bool:
    """Run one instrumented serial pass and print its failure summary."""
    for path in REPORT_DIR.glob("report-*.json"):
        path.unlink()
    env = dict(os.environ)
    env["PYTEST_PLUGINS"] = "pytest_suite_os_probe"
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{PLUGIN_DIR}{os.pathsep}{existing}" if existing else str(PLUGIN_DIR)
    )
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=line", *extra_args],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    elapsed = time.perf_counter() - start
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    tail = lines[-1][:160] if lines else ""
    print(f"\n=== {label}: wall {elapsed:.2f}s rc={result.returncode} {tail}")
    failed = [line for line in lines if line.startswith("FAILED")]
    print(f"failed lines: {len(failed)}")
    for line in failed[:40]:
        print("  ", line[:220])
    return result.returncode == 0


def summarize_single_process() -> None:
    """Print the serial report's phase totals and heaviest operations."""
    reports = sorted(REPORT_DIR.glob("report-*.json"))
    print(f"reports written: {len(reports)}")
    for path in reports:
        payload = json.loads(path.read_text(encoding="utf-8"))
        print(
            f"pid={payload['pid']} is_worker={payload['is_worker']} "
            f"call_reports={payload['call_reports']} "
            f"sleep={payload['sleep_seconds']:.2f}s"
        )
        for name, phase in payload["phase"].items():
            print(
                f"  phase {name}: reports={phase['reports']} "
                f"seconds={phase['seconds']:.2f}"
            )
        operation_seconds = Counter(payload["op_seconds"])
        for operation, count in sorted(
            payload["ops_total"].items(),
            key=lambda item: item[1],
            reverse=True,
        )[:10]:
            print(
                f"  op {operation}: calls={count} "
                f"inside={operation_seconds[operation]:.2f}s"
            )
        for item in payload["op_heavy"][:5]:
            print(
                f"  heavy {item['ops']} ops call {item['seconds']:.2f}s "
                f"{item['nodeid'][:120]}"
            )


def main() -> None:
    """Run the serial instrumented pass, then print its report."""
    print("cpu_count", os.cpu_count())
    clean = run_serial(
        "serial plugin, timeout disabled", ["-n", "0", "--timeout=0"]
    )
    summarize_single_process()
    if clean:
        print("VERDICT: the wrapper is safe when the timeout is disabled")
    else:
        print("VERDICT: the wrapper breaks tests independently of the timeout")


if __name__ == "__main__":
    main()