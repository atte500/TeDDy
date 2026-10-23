"""Measure the Windows editor launcher chain against the native GUI binary.

The configured editor resolves to a batch wrapper. This spike times the PATH
resolution, the batch wrapper through cmd.exe plus the node bootstrap, and the
native GUI binary, so the launch chain cost is separated from our own code.
"""

from __future__ import annotations

import shutil
import subprocess  # nosec B404
import sys
import time
from pathlib import Path

TIMEOUT_SECONDS = 90


def timed(label: str, args: list[str]) -> float | None:
    """Run one command and print its wall-clock duration."""
    start = time.perf_counter()
    kwargs: dict = {"capture_output": True, "timeout": TIMEOUT_SECONDS}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run(args, **kwargs)  # nosec B603
    except Exception as exc:  # report every failure shape, keep measuring
        elapsed = time.perf_counter() - start
        print(f"{label}: {elapsed:.3f}s FAILED {type(exc).__name__}: {exc}")
        return None
    elapsed = time.perf_counter() - start
    output = result.stdout.decode("utf-8", errors="replace").strip().splitlines()
    first = output[0] if output else ""
    print(f"{label}: {elapsed:.3f}s rc={result.returncode} out={first[:70]!r}")
    return elapsed


def main() -> int:
    """Time resolution and both bootstraps twice to separate cold from warm."""
    resolve_start = time.perf_counter()
    launcher = shutil.which("codium")
    resolve_elapsed = time.perf_counter() - resolve_start
    print(f"which(codium): {resolve_elapsed:.3f}s -> {launcher}")
    if not launcher:
        print("SKIP: codium is not on PATH on this host.")
        return 1

    native = Path(launcher).resolve().parent.parent / "VSCodium.exe"
    print(f"native candidate: {native} exists={native.exists()}")

    timed("launcher --version (cold)", [launcher, "--version"])
    timed("launcher --version (warm)", [launcher, "--version"])
    if native.exists():
        timed("native --version (cold)", [str(native), "--version"])
        timed("native --version (warm)", [str(native), "--version"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())