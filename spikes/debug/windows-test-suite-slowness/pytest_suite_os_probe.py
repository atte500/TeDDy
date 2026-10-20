"""Pytest plugin recording worker timelines and operating-system call volume.

The runner loads this module through ``PYTEST_PLUGINS``. Every pytest process,
controller or xdist worker, writes one JSON report into the system temp
directory. A report holds the process timeline, the per-phase totals, the
accumulated sleep seconds, the operating-system call counts together with the
seconds spent inside each call, and the slowest or most call-heavy tests.
Reports stay outside the repository because the session-scoped pollution guard
fails on any new tree entry.
"""

import builtins
import functools
import io
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

REPORT_DIR = Path(tempfile.gettempdir()) / "teddy-suite-os-probe"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

_PHASE = {"name": "collection", "nodeid": None}
_OPS = {}
_COUNTS = {}
_OP_SECONDS = {}
_PHASE_OPS = {}
_PHASE_SECONDS = {}
_PHASE_REPORTS = {}
_CALL_SECONDS = {}
_SLEEP_SECONDS = 0.0
_SESSION_START_WALL = 0.0
_FIRST_TEST_WALL = 0.0
_LAST_REPORT_WALL = 0.0


def _bump(operation):
    """Record one call for the current test and phase."""
    nodeid = _PHASE["nodeid"] or "<collection>"
    bucket = _OPS.get(nodeid)
    if bucket is None:
        bucket = _OPS[nodeid] = {}
    bucket[operation] = bucket.get(operation, 0) + 1
    _COUNTS[operation] = _COUNTS.get(operation, 0) + 1
    phase = _PHASE["name"]
    phase_bucket = _PHASE_OPS.get(phase)
    if phase_bucket is None:
        phase_bucket = _PHASE_OPS[phase] = {}
    phase_bucket[operation] = phase_bucket.get(operation, 0) + 1


def _add_seconds(operation, seconds):
    """Accumulate the measured time inside one operation."""
    _OP_SECONDS[operation] = _OP_SECONDS.get(operation, 0.0) + seconds


def _wrap(module, name, operation):
    """Replace one module callable with a counting and timing wrapper."""
    original = getattr(module, name, None)
    if original is None or getattr(original, "_teddy_probe_wrapped", False):
        return

    @functools.wraps(original)
    def wrapper(*args, **kwargs):
        _bump(operation)
        start = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            _add_seconds(operation, time.perf_counter() - start)

    wrapper._teddy_probe_wrapped = True
    setattr(module, name, wrapper)


for _name, _operation in (
    ("stat", "stat"),
    ("lstat", "stat"),
    ("listdir", "listdir"),
    ("scandir", "scandir"),
    ("mkdir", "mkdir"),
    ("makedirs", "mkdir"),
    ("remove", "remove"),
    ("unlink", "remove"),
    ("rmdir", "rmdir"),
    ("rename", "rename"),
    ("replace", "rename"),
    ("chdir", "chdir"),
    ("getcwd", "getcwd"),
):
    _wrap(os, _name, _operation)

_ORIGINAL_IO_OPEN = io.open


@functools.wraps(_ORIGINAL_IO_OPEN)
def _timed_open(*args, **kwargs):
    _bump("open")
    start = time.perf_counter()
    try:
        return _ORIGINAL_IO_OPEN(*args, **kwargs)
    finally:
        _add_seconds("open", time.perf_counter() - start)


io.open = _timed_open
builtins.open = _timed_open

_ORIGINAL_POPEN_INIT = subprocess.Popen.__init__


@functools.wraps(_ORIGINAL_POPEN_INIT)
def _timed_popen_init(self, *args, **kwargs):
    _bump("spawn")
    start = time.perf_counter()
    try:
        return _ORIGINAL_POPEN_INIT(self, *args, **kwargs)
    finally:
        _add_seconds("spawn", time.perf_counter() - start)


subprocess.Popen.__init__ = _timed_popen_init

_ORIGINAL_SLEEP = time.sleep


@functools.wraps(_ORIGINAL_SLEEP)
def _timed_sleep(seconds):
    global _SLEEP_SECONDS
    _SLEEP_SECONDS += seconds
    return _ORIGINAL_SLEEP(seconds)


time.sleep = _timed_sleep


def pytest_sessionstart(session):
    """Record the session wall-clock origin for the worker timeline."""
    global _SESSION_START_WALL
    _SESSION_START_WALL = time.time()


def pytest_runtest_setup(item):
    """Mark the setup phase and remember the first test start."""
    global _FIRST_TEST_WALL
    _PHASE["name"] = "setup"
    _PHASE["nodeid"] = item.nodeid
    if not _FIRST_TEST_WALL:
        _FIRST_TEST_WALL = time.time()


def pytest_runtest_call(item):
    """Mark the call phase."""
    _PHASE["name"] = "call"


def pytest_runtest_teardown(item):
    """Mark the teardown phase."""
    _PHASE["name"] = "teardown"


def pytest_runtest_logreport(report):
    """Accumulate phase totals and remember the newest report wall clock."""
    global _LAST_REPORT_WALL
    _LAST_REPORT_WALL = time.time()
    _PHASE_SECONDS[report.when] = _PHASE_SECONDS.get(report.when, 0.0) + report.duration
    _PHASE_REPORTS[report.when] = _PHASE_REPORTS.get(report.when, 0) + 1
    if report.when == "call":
        _CALL_SECONDS[report.nodeid] = report.duration


def pytest_sessionfinish(session, exitstatus):
    """Write this process report once, from every controller and worker."""
    op_heavy = []
    for nodeid, operations in _OPS.items():
        total = sum(operations.values())
        if not total:
            continue
        op_heavy.append(
            {
                "nodeid": nodeid,
                "ops": total,
                "seconds": _CALL_SECONDS.get(nodeid, 0.0),
                "by_op": operations,
            }
        )
    op_heavy.sort(key=lambda item: item["ops"], reverse=True)
    slow_calls = sorted(
        _CALL_SECONDS.items(), key=lambda item: item[1], reverse=True
    )[:12]
    payload = {
        "pid": os.getpid(),
        "is_worker": hasattr(session.config, "workerinput"),
        "session_start_wall": _SESSION_START_WALL,
        "session_end_wall": time.time(),
        "first_test_wall": _FIRST_TEST_WALL,
        "last_report_wall": _LAST_REPORT_WALL,
        "exitstatus": int(exitstatus),
        "call_reports": _PHASE_REPORTS.get("call", 0),
        "phase": {
            name: {
                "reports": _PHASE_REPORTS.get(name, 0),
                "seconds": _PHASE_SECONDS.get(name, 0.0),
            }
            for name in ("setup", "call", "teardown")
        },
        "sleep_seconds": _SLEEP_SECONDS,
        "ops_total": _COUNTS,
        "op_seconds": _OP_SECONDS,
        "ops_by_phase": _PHASE_OPS,
        "op_heavy": op_heavy[:12],
        "slow_calls": [
            {"nodeid": nodeid, "seconds": seconds} for nodeid, seconds in slow_calls
        ],
    }
    path = REPORT_DIR / f"report-{os.getpid()}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")