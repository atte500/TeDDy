"""Measure whether the parallel suite saturates the CPU and whether Defender scans.

The uninstrumented worker curve plateaus near 3.3x on twelve logical CPUs and
never improves past eight workers. That shape means either a serialized shared
resource or a throughput ceiling below the physical core count. This probe
records the whole-system CPU busy fraction through the Win32 GetSystemTimes API
while the suite runs at eight workers, reads the Defender configuration, and
benchmarks small-file churn in the system temp directory and in any excluded
directory that Defender already trusts. The sampler calls a kernel API instead
of wrapping ``os``, so it cannot disturb the pyfakefs patcher.
"""

import ctypes
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Sequence
from ctypes import wintypes
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHURN_FILES = 400
PAYLOAD = "x" * 1024
SAMPLE_INTERVAL_SECONDS = 0.5


class _FileTime(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]


def _to_int(value: "_FileTime") -> int:
    return (value.dwHighDateTime << 32) | value.dwLowDateTime


def _system_times() -> tuple[int, int, int]:
    """Return the idle, kernel, and user tick counters for the whole system."""
    idle = _FileTime()
    kernel = _FileTime()
    user = _FileTime()
    if not ctypes.windll.kernel32.GetSystemTimes(
        ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
    ):
        raise ctypes.WinError()
    return _to_int(idle), _to_int(kernel), _to_int(user)


class CpuSampler(threading.Thread):
    """Samples the whole-system busy fraction until stopped."""

    def __init__(self, interval: float = SAMPLE_INTERVAL_SECONDS) -> None:
        super().__init__(daemon=True)
        self.interval = interval
        self.samples: list[float] = []
        # The event is deliberately not named ``_stop``: Thread.join() calls
        # the private Thread._stop() method, so an attribute with that name
        # replaces the method and makes join() raise a TypeError.
        self._stop_event = threading.Event()

    def run(self) -> None:
        previous = _system_times()
        while not self._stop_event.wait(self.interval):
            current = _system_times()
            idle_delta = current[0] - previous[0]
            total_delta = (current[1] - previous[1]) + (current[2] - previous[2])
            if total_delta > 0:
                busy = 1.0 - idle_delta / total_delta
                self.samples.append(max(0.0, min(1.0, busy)))
            previous = current

    def stop(self) -> None:
        self._stop_event.set()


def _resolve_powershell() -> list[str] | None:
    """Resolve the PowerShell executable, which can sit off the inherited PATH."""
    for candidate in ("powershell.exe", "powershell", "pwsh"):
        found = shutil.which(candidate)
        if found:
            return [found]
    fallback = (
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    if fallback.is_file():
        return [str(fallback)]
    return None


def powershell(script: str) -> str:
    """Run one PowerShell expression and return its trimmed output."""
    command = _resolve_powershell()
    if command is None:
        return "unavailable (no PowerShell executable found)"
    try:
        result = subprocess.run(
            [*command, "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"unavailable ({error})"
    if result.returncode != 0:
        return f"error ({result.stderr.strip()[:200]})"
    return result.stdout.strip()


def parse_paths(raw: str) -> list[str]:
    """Parse a ConvertTo-Json value that may be null, a scalar, or a list."""
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence):
        return [str(item) for item in value]
    return []


def churn(root: Path, label: str) -> None:
    """Create, stat, and delete a fixed number of small files."""
    start = time.perf_counter()
    for index in range(CHURN_FILES):
        path = root / f"churn_{index}.txt"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(PAYLOAD)
        path.stat()
        path.unlink()
    elapsed = time.perf_counter() - start
    each = elapsed / CHURN_FILES * 1000
    print(f"churn {label}: {elapsed:.3f}s total, {each:.3f}ms per file")


def churn_temp() -> None:
    """Benchmark churn in the system temp directory, cold and warm."""
    root = Path(tempfile.mkdtemp(prefix="teddy-churn-temp-"))
    try:
        churn(root, "system temp (cold)")
        churn(root, "system temp (warm)")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def churn_excluded(raw: str) -> None:
    """Benchmark churn inside Defender's first writable excluded directory."""
    for candidate in parse_paths(raw):
        path = Path(candidate)
        if not path.is_dir():
            continue
        try:
            root = Path(tempfile.mkdtemp(prefix="teddy-churn-excluded-", dir=str(path)))
        except OSError as error:
            print(f"excluded {candidate}: not writable ({error})")
            continue
        try:
            churn(root, f"excluded dir {candidate} (cold)")
            churn(root, f"excluded dir {candidate} (warm)")
        finally:
            shutil.rmtree(root, ignore_errors=True)
        return
    print("no writable Defender exclusion directory found")


def run_idle_sample(seconds: float) -> None:
    """Measure the background busy fraction with no suite running."""
    sampler = CpuSampler()
    sampler.start()
    time.sleep(seconds)
    sampler.stop()
    sampler.join(timeout=5)
    if not sampler.samples:
        print("cpu busy idle: no samples collected")
        return
    ordered = sorted(sampler.samples)
    print(
        f"cpu busy idle: samples={len(ordered)} "
        f"mean={statistics.fmean(ordered):.3f} "
        f"p50={statistics.median(ordered):.3f} max={ordered[-1]:.3f}"
    )


def run_sampled_suite(workers: int) -> None:
    """Run the suite at the given width while sampling the CPU busy fraction."""
    sampler = CpuSampler()
    sampler.start()
    start = time.perf_counter()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-n", str(workers)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
    finally:
        sampler.stop()
        sampler.join(timeout=5)
    elapsed = time.perf_counter() - start
    tail_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    tail = tail_lines[-1][:140] if tail_lines else ""
    print(f"suite -n {workers}: {elapsed:.2f}s rc={result.returncode} tail={tail}")
    if not sampler.samples:
        print("cpu busy: no samples collected")
        return
    ordered = sorted(sampler.samples)
    mean = statistics.fmean(ordered)
    p10 = ordered[len(ordered) // 10]
    p50 = statistics.median(ordered)
    p90 = ordered[(len(ordered) * 9) // 10]
    print(
        f"cpu busy: samples={len(ordered)} mean={mean:.3f} "
        f"p10={p10:.3f} p50={p50:.3f} p90={p90:.3f} "
        f"min={ordered[0]:.3f} max={ordered[-1]:.3f}"
    )
    print("cpu busy first samples:", [f"{value:.2f}" for value in sampler.samples[:12]])


def main() -> None:
    """Report the host, the Defender configuration, churn cost, and CPU load."""
    if os.name != "nt":
        print("GetSystemTimes sampling is only available on Windows")
        return
    print("cpu_count", os.cpu_count())
    print("platform_processor", platform.processor())
    print("powershell", _resolve_powershell())
    print(
        "processor",
        powershell(
            "Get-CimInstance Win32_Processor | "
            "Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed | "
            "ConvertTo-Json -Compress"
        ),
    )
    print(
        "defender status",
        powershell(
            "Get-MpComputerStatus | "
            "Select-Object AntivirusEnabled,RealTimeProtectionEnabled,IsTamperProtected | "
            "ConvertTo-Json -Compress"
        ),
    )
    exclusions_raw = powershell(
        "(Get-MpPreference).ExclusionPath | ConvertTo-Json -Compress"
    )
    print("defender exclusion paths", exclusions_raw)
    print(
        "defender exclusion extensions",
        powershell("(Get-MpPreference).ExclusionExtension | ConvertTo-Json -Compress"),
    )
    print(
        "defender exclusion processes",
        powershell("(Get-MpPreference).ExclusionProcess | ConvertTo-Json -Compress"),
    )

    churn_temp()
    churn_excluded(exclusions_raw)

    start = time.perf_counter()
    checksum = sum(index * index for index in range(2_000_000))
    elapsed = time.perf_counter() - start
    print(
        f"python cpu benchmark: sum of squares to 2,000,000 in {elapsed:.3f}s "
        f"(checksum {checksum})"
    )

    run_idle_sample(10.0)
    run_sampled_suite(8)


if __name__ == "__main__":
    main()