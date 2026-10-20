"""Pytest plugin recording each test's wall-clock window in every process.

The runner loads this module through ``PYTEST_PLUGINS``. Every process,
controller or xdist worker, writes one JSON report into the system temp
directory. A report holds the process wall-clock origin plus each report's
start offset and duration, which is enough to reconstruct worker start
staggering, per-worker busy time, idle capacity, and the tail after the last
test. No ``os`` attribute is wrapped, so the pyfakefs patcher stays
undisturbed, unlike the rejected syscall plugin.
"""

import json
import os
import tempfile
import time
from pathlib import Path

REPORT_DIR = Path(tempfile.gettempdir()) / "teddy-parallel-timeline"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

_SESSION_START_WALL = 0.0
_REPORTS: list[tuple[str, float, float]] = []


def pytest_sessionstart(session):
    """Record this process's wall-clock origin."""
    global _SESSION_START_WALL
    _SESSION_START_WALL = time.time()


def pytest_runtest_logreport(report):
    """Record one phase report with its offset from this process's start."""
    _REPORTS.append((report.when, report.start, report.duration))


def pytest_sessionfinish(session, exitstatus):
    """Write this process's timeline report exactly once."""
    payload = {
        "pid": os.getpid(),
        "is_worker": hasattr(session.config, "workerinput"),
        "session_start_wall": _SESSION_START_WALL,
        "session_end_wall": time.time(),
        "exitstatus": int(exitstatus),
        "reports": _REPORTS,
    }
    path = REPORT_DIR / f"timeline-{os.getpid()}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")