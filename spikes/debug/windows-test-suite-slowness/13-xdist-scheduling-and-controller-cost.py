"""Separate xdist controller serialization from worker-side contention.

Probe 12 measured this host's pure-Python ceiling at 5.33x for eight
processes and 6.06x for twelve, while the suite reaches only 3.26x and
3.19x. The suite therefore loses roughly half the machine throughput, and
a two-term fit leaves about 19s of wall clock that no worker count removes.
A pytest controller that serializes per-test dispatch or result processing
produces exactly that shape, because its cost scales with the test count
and not with the worker count. This probe compares the default per-test
scheduler against chunked schedulers that cut dispatch volume, and it
samples the controller process's own CPU time. A material wall-clock drop
with chunked dispatch, or a controller pinned near one busy core, confirms
the serialization. All runs execute the same suite and must pass.
"""

import ctypes
import os
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

RUNS = (
    ("n8 load", ("-q", "-n", "8")),
    ("n8 loadfile", ("-q", "-n", "8", "--dist", "loadfile")),
    ("n8 loadscope", ("-q", "-n", "8", "--dist", "loadscope")),
    ("n8 worksteal", ("-q", "-n", "8", "--dist", "worksteal")),
    ("n4 loadfile", ("-q", "-n", "4", "--dist", "loadfile")),
)


class _FileTime(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]


def _filetime_to_int(value: "_FileTime") -> int:
    return (value.dwHighDateTime << 32) | value.dwLowDateTime


def controller_cpu_seconds(handle: int) -> float | None:
    """Read the kernel plus user CPU seconds of one process."""
    creation = _FileTime()
    exit_time = _FileTime()
    kernel = _FileTime()
    user = _FileTime()
    ok = ctypes.windll.kernel32.GetProcessTimes(
        wintypes.HANDLE(handle),
        ctypes.byref(creation),
        ctypes.byref(exit_time),
        ctypes.byref(kernel),
        ctypes.byref(user),
    )
    if not ok:
        return None
    return (_filetime_to_int(kernel) + _filetime_to_int(user)) / 10_000_000


def run_suite(label: str, args: tuple[str, ...], timeout: int = 600) -> None:
    """Run one suite pass and report wall clock plus controller CPU load."""
    start = time.perf_counter()
    popen = subprocess.Popen(
        [sys.executable, "-m", "pytest", *args],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    )
    samples: list[float] = []
    stop_event = threading.Event()

    def sample_controller() -> None:
        while not stop_event.wait(0.25):
            seconds = controller_cpu_seconds(int(popen._handle))
            if seconds is not None:
                samples.append(seconds)

    sampler = threading.Thread(target=sample_controller, daemon=True)
    sampler.start()
    timed_out = False
    try:
        stdout, stderr = popen.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        popen.kill()
        stdout, stderr = popen.communicate()
    finally:
        stop_event.set()
        sampler.join(timeout=2)
    elapsed = time.perf_counter() - start

    lines = [line.strip() for line in (stdout or "").splitlines() if line.strip()]
    tail = lines[-1][:140] if lines else ""
    controller_cpu = samples[-1] if samples else 0.0
    utilization = controller_cpu / elapsed if elapsed else 0.0
    print(
        f"{label}: wall {elapsed:.2f}s rc={popen.returncode} "
        f"controller_cpu {controller_cpu:.2f}s ({utilization:.0%} of one core) "
        f"tail={tail}"
    )
    if timed_out:
        print(f"{label}: TIMEOUT after {elapsed:.2f}s")
        return
    if popen.returncode != 0:
        error_lines = [
            line.strip() for line in (stderr or "").splitlines() if line.strip()
        ]
        if error_lines:
            print(f"  stderr: {error_lines[-1][:240]}")


def main() -> None:
    """Run each scheduling mode and print its wall clock and controller load."""
    print("cpu_count", os.cpu_count())
    print("python", sys.version.split()[0])
    print("project root", PROJECT_ROOT)
    for label, args in RUNS:
        run_suite(label, args)


if __name__ == "__main__":
    main()