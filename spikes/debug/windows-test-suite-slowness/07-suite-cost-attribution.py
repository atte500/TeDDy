"""Run the full suite serially with the cost-attribution plugin.

The plugin measures setup, call, and teardown phases plus process creation and
temporary workspace churn. A serial run keeps every measurement in one process,
so the phase totals can be compared directly against the 93s serial duration
reported by probe 06.
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = Path(__file__).resolve().parent
REPORT_PATH = Path(tempfile.gettempdir()) / "teddy-suite-cost-report.txt"


def main():
    """Run pytest with the plugin and print the report it produced."""
    print("cpu_count", os.cpu_count())
    print("plugin dir", PLUGIN_DIR)
    env = dict(os.environ)
    env["PYTEST_PLUGINS"] = "pytest_suite_cost_probe"
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{PLUGIN_DIR}{os.pathsep}{existing}" if existing else str(PLUGIN_DIR)
    )
    REPORT_PATH.unlink(missing_ok=True)

    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-n", "0", "-q"],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    elapsed = time.perf_counter() - start
    stdout_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    tail = stdout_lines[-1][:140] if stdout_lines else ""
    print(f"pytest wall: {elapsed:.2f}s rc={result.returncode} tail={tail}")
    if result.returncode != 0:
        for line in result.stderr.splitlines()[-6:]:
            print("stderr:", line[:240])

    if REPORT_PATH.exists():
        print(REPORT_PATH.read_text(encoding="utf-8"))
    else:
        print("report missing; the plugin did not load")


if __name__ == "__main__":
    main()