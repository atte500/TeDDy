"""Probe: measure the real synchronous cost of launching codium.CMD.

The annotated diff path calls ``_run_editor_process`` synchronously on Windows,
so the Textual event loop stays blocked until the editor launcher returns. This
probe times the resolved ``codium.CMD`` launcher twice: a cold start and a warm
start that attaches to the already running instance. It never terminates
Codium, so any editor window the probe opens stays open for the user.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Any, Optional


def _bootstrap_src() -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    src = os.path.join(root, "src")
    if src not in sys.path:
        sys.path.insert(0, src)


_bootstrap_src()

from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
from teddy_executor.adapters.outbound.system_environment_adapter import (
    SystemEnvironmentAdapter,
)


class _ConfigStub:
    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)


CREATE_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TIMEOUT_SECONDS = 60


def _time_sync_launch(cmd: list[str], label: str) -> Optional[float]:
    """Run the launcher synchronously and return the elapsed seconds."""
    start = time.perf_counter()
    try:
        subprocess.run(  # noqa: S603
            cmd,
            creationflags=CREATE_FLAGS,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - start
        print(f"{label:<12} still running after {elapsed:.2f}s (timeout)")
        return None
    elapsed = time.perf_counter() - start
    print(f"{label:<12} return = {elapsed * 1000:.2f}ms")
    return elapsed


def main() -> int:
    print(f"platform={sys.platform}")
    print("This probe opens a real editor window and leaves it open.")

    env = SystemEnvironmentAdapter()
    tooling = ConsoleToolingHelper(env, _ConfigStub({"editor": "codium"}))
    editor_cmd = tooling.find_editor()
    if not editor_cmd:
        print("no editor resolved; nothing to measure")
        return 1

    print(f"resolved editor = {editor_cmd[0]!r}")

    temp_path = env.create_temp_file(suffix=".diff")
    with open(temp_path, "w", encoding="utf-8") as handle:
        handle.write("--- probe (original)\n+++ probe (proposed)\n context\n")

    # Mirrors the production annotated branch: editor path plus the file.
    sync_cmd = list(editor_cmd[:1]) + [temp_path]

    print("\n--- synchronous launch cost (what the Windows annotated path pays) ---")
    cold = _time_sync_launch(sync_cmd, "cold run")
    time.sleep(2)
    warm = _time_sync_launch(sync_cmd, "warm run")

    print("\n--- interpretation ---")
    for label, value in (("cold", cold), ("warm", warm)):
        if value is None:
            print(f"{label}: launcher did not return, so the TUI would freeze")
        elif value >= 0.1:
            print(f"{label}: {value * 1000:.0f}ms of blocked event loop is perceptible")
        else:
            print(f"{label}: {value * 1000:.0f}ms of block is below the stutter threshold")

    try:
        os.unlink(temp_path)
    except OSError:
        # The editor may still hold the file open; the OS temp dir is cleaned up later.
        pass

    print("\ndone")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())