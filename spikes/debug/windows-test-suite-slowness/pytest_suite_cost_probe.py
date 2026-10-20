"""Pytest plugin that attributes suite wall clock to phases and OS primitives.

The accompanying runner loads this module through ``PYTEST_PLUGINS`` and reads
the summary it writes to the system temp directory. The wrappers are installed
at import time, before any test body runs, so every spawn and workspace
operation in the suite is counted. The report stays outside the repository
because the session-scoped pollution guard fails on any new tree entry.
"""

import shutil
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path

REPORT_PATH = Path(tempfile.gettempdir()) / "teddy-suite-cost-report.txt"

_ORIGINAL_POPEN_INIT = subprocess.Popen.__init__
_ORIGINAL_MKDTEMP = tempfile.mkdtemp
_ORIGINAL_RMTREE = shutil.rmtree

_CALL_COUNTS: Counter = Counter()
_CALL_SECONDS: Counter = Counter()
_PHASE_SECONDS: Counter = Counter()
_PHASE_COUNTS: Counter = Counter()
_REPORTS = []
_SESSION_START = 0.0


def _record(label, seconds):
    """Accumulate one primitive call into its count and second buckets."""
    _CALL_COUNTS[label] += 1
    _CALL_SECONDS[label] += seconds


def _timed_popen_init(self, *args, **kwargs):
    start = time.perf_counter()
    try:
        return _ORIGINAL_POPEN_INIT(self, *args, **kwargs)
    finally:
        _record("subprocess_spawn", time.perf_counter() - start)


def _timed_mkdtemp(*args, **kwargs):
    start = time.perf_counter()
    try:
        return _ORIGINAL_MKDTEMP(*args, **kwargs)
    finally:
        _record("tempfile_mkdtemp", time.perf_counter() - start)


def _timed_rmtree(*args, **kwargs):
    start = time.perf_counter()
    try:
        return _ORIGINAL_RMTREE(*args, **kwargs)
    finally:
        _record("shutil_rmtree", time.perf_counter() - start)


subprocess.Popen.__init__ = _timed_popen_init
tempfile.mkdtemp = _timed_mkdtemp
shutil.rmtree = _timed_rmtree


def pytest_sessionstart(session):
    """Record the wall-clock origin of the session."""
    global _SESSION_START
    _SESSION_START = time.perf_counter()


def pytest_runtest_logreport(report):
    """Accumulate one phase report and keep it for the slowest ranking."""
    _PHASE_SECONDS[report.when] += report.duration
    _PHASE_COUNTS[report.when] += 1
    _REPORTS.append((report.duration, report.when, report.nodeid))


def _call_histogram():
    """Bucket call-phase durations so a fixed per-test floor is visible."""
    edges = (0.005, 0.01, 0.02, 0.05, 0.1, 0.25, 0.5)
    buckets = Counter()
    for seconds, when, _nodeid in _REPORTS:
        if when != "call":
            continue
        for edge in edges:
            if seconds < edge:
                buckets[f"call<{edge * 1000:.0f}ms"] += 1
                break
        else:
            buckets["call>=500ms"] += 1
    return buckets


def pytest_sessionfinish(session, exitstatus):
    """Write the aggregated summary once, from the controller process only."""
    if hasattr(session.config, "workerinput"):
        return
    lines = [f"exitstatus {exitstatus}"]
    lines.append(f"wall_seconds {time.perf_counter() - _SESSION_START:.2f}")
    for phase in ("setup", "call", "teardown"):
        seconds = _PHASE_SECONDS[phase]
        count = _PHASE_COUNTS[phase]
        average = seconds / count if count else 0.0
        lines.append(
            f"phase {phase}: count={count} seconds={seconds:.2f} avg={average:.4f}"
        )
    lines.append(f"phase total: {sum(_PHASE_SECONDS.values()):.2f}")
    for label in sorted(_CALL_COUNTS):
        seconds = _CALL_SECONDS[label]
        count = _CALL_COUNTS[label]
        average = seconds / count if count else 0.0
        lines.append(
            f"primitive {label}: calls={count} seconds={seconds:.2f} avg={average:.4f}"
        )
    for bucket, count in sorted(_call_histogram().items()):
        lines.append(f"histogram {bucket}: {count}")
    lines.append("slowest:")
    for seconds, when, nodeid in sorted(_REPORTS, reverse=True)[:40]:
        lines.append(f"  {seconds:.3f}s {when} {nodeid}")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")