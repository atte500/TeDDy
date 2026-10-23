"""Separate our editor spawn cost from the editor's own dispatch chain.

``spawn_editor`` returns as soon as ``subprocess.Popen`` hands the launch to
the operating system. This spike records that return time next to the full
chain completion time for the same launcher command and the same
``CREATE_NO_WINDOW`` flag, so the editor-open latency is attributed to our
spawn call or to the editor chain.
"""

from __future__ import annotations

import shutil
import subprocess  # nosec B404
import sys
import time
from pathlib import Path

TIMEOUT_SECONDS = 120


def _popen_kwargs() -> dict[str, object]:
    """Mirror the flags that the editor spawn path uses on this platform."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def _spawn_and_wait(label: str, args: list[str]) -> None:
    """Run one command and report the spawn return time and the chain total."""
    kwargs = _popen_kwargs()
    start = time.perf_counter()
    process = subprocess.Popen(args, **kwargs)  # nosec B603
    returned = time.perf_counter() - start
    try:
        process.wait(timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        print(f"{label}: spawn_return={returned:.3f}s chain_total=TIMEOUT")
        return
    completed = time.perf_counter() - start
    print(
        f"{label}: spawn_return={returned:.3f}s "
        f"chain_total={completed:.3f}s rc={process.returncode}"
    )


def main() -> int:
    """Measure the launcher chain and the native binary in one pass."""
    launcher = shutil.which("codium")
    print(f"which(codium): {launcher}")
    if not launcher:
        print("SKIP: codium is not on PATH on this host.")
        return 1
    native = Path(launcher).resolve().parent.parent / "VSCodium.exe"
    print(f"native: {native} exists={native.exists()}")

    _spawn_and_wait("launcher --version", [launcher, "--version"])
    _spawn_and_wait("launcher --status", [launcher, "--status"])
    if native.exists():
        _spawn_and_wait("native --version", [str(native), "--version"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())