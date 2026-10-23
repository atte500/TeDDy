"""Measure the Windows editor dispatch against the native GUI binary.

The batch launcher wraps a node CLI bootstrap. This spike records whether a
VSCodium instance is already running, the node CLI dispatch cost through the
batch wrapper, and the native GUI binary cost, so the editor-open latency is
attributed to the dispatch chain or to the editor's own GUI startup. It runs
only non-intrusive commands and opens no editor window.
"""

from __future__ import annotations

import shutil
import subprocess  # nosec B404
import sys
import time
from pathlib import Path

TIMEOUT_SECONDS = 90
NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def running_vscodium() -> str:
    """Report whether a VSCodium GUI process is already running."""
    if sys.platform != "win32":
        return "not-win32"
    try:
        result = subprocess.run(  # nosec B603
            ["tasklist", "/FI", "IMAGENAME eq VSCodium.exe"],
            capture_output=True,
            timeout=30,
            creationflags=NO_WINDOW,
        )
    except Exception as exc:  # report the failure shape and continue
        return f"probe-failed:{type(exc).__name__}"
    text = result.stdout.decode("utf-8", errors="replace")
    return "running" if "VSCodium.exe" in text else "not-running"


def timed(label: str, args: list[str]) -> None:
    """Run one command and print its wall-clock duration and first output line."""
    start = time.perf_counter()
    try:
        result = subprocess.run(  # nosec B603
            args, capture_output=True, timeout=TIMEOUT_SECONDS, creationflags=NO_WINDOW
        )
    except Exception as exc:  # report every failure shape, keep measuring
        elapsed = time.perf_counter() - start
        print(f"{label}: {elapsed:.3f}s FAILED {type(exc).__name__}: {exc}")
        return
    elapsed = time.perf_counter() - start
    raw = result.stdout or result.stderr or b""
    lines = raw.decode("utf-8", errors="replace").strip().splitlines()
    first = lines[0] if lines else ""
    print(f"{label}: {elapsed:.3f}s rc={result.returncode} out={first[:70]!r}")


def main() -> int:
    """Report the editor state and time the dispatch chain without opening a window."""
    launcher = shutil.which("codium")
    print(f"which(codium): {launcher}")
    if not launcher:
        print("SKIP: codium is not on PATH on this host.")
        return 1
    print(f"vscodium: {running_vscodium()}")
    native = Path(launcher).resolve().parent.parent / "VSCodium.exe"
    print(f"native: {native} exists={native.exists()}")

    timed("launcher --status", [launcher, "--status"])
    timed("launcher --version", [launcher, "--version"])
    if native.exists():
        timed("native --version", [str(native), "--version"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())