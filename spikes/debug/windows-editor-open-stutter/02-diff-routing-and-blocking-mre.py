"""Probe: prove the .cmd extension misroutes codium and blocks the event loop.

Windows resolves the configured GUI editor to ``codium.CMD``. The editor
routing compares ``os.path.basename(...)`` (or its lowercase form) against
tables keyed on extension-less names (``_DIFF_FLAGS``, ``_CLI_EDITORS``, the
vim set). The ``.CMD`` suffix therefore misses every lookup. This probe shows
(1) the diff command is returned without diff flags, (2) the annotated diff
path is selected, and (3) that path runs the editor synchronously, blocking
the caller for the whole launcher duration while a background spawn returns
in milliseconds.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Any


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
from teddy_executor.adapters.inbound.textual_plan_reviewer_editor import (
    _is_cli_editor,
    _is_vim_editor,
    _run_editor_process,
    _uses_annotated_diff_path,
)


class _ConfigStub:
    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)


CREATE_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _simulated_gui_launcher(directory: str, sleep_seconds: int) -> str:
    """Create a .cmd that blocks for roughly ``sleep_seconds`` seconds."""
    path = os.path.join(directory, "slowgui.cmd")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("@echo off\r\n")
        handle.write(f"ping -n {sleep_seconds} 127.0.0.1 >nul\r\n")
        handle.write("exit /b 0\r\n")
    return path


def main() -> None:
    print(f"platform={sys.platform}")

    env = SystemEnvironmentAdapter()
    tooling = ConsoleToolingHelper(env, _ConfigStub({"editor": "codium"}))

    diff_viewer = tooling.get_diff_viewer_command()
    assert diff_viewer, "expected a resolved diff viewer"
    real_base = os.path.basename(diff_viewer[0])
    real_key = real_base.lower()
    print("\n--- routing decision for the real resolved command ---")
    print(f"diff_viewer          = {diff_viewer!r}")
    print(f"basename             = {real_base!r}")
    print(f"lowercased           = {real_key!r}")
    print(f"in _DIFF_FLAGS?      = {real_key in ConsoleToolingHelper._DIFF_FLAGS}")
    print(f"_is_cli_editor?      = {_is_cli_editor(diff_viewer)}")
    print(f"_is_vim_editor?      = {_is_vim_editor(diff_viewer)}")
    print(f"uses_annotated_diff? = {_uses_annotated_diff_path(diff_viewer)}")

    stripped = [os.path.splitext(diff_viewer[0])[0]]
    stripped_base = os.path.basename(stripped[0]).lower()
    print("\n--- routing decision with the Windows extension stripped ---")
    print(f"stripped command     = {stripped!r}")
    print(f"basename             = {stripped_base!r}")
    print(f"in _DIFF_FLAGS?      = {stripped_base in ConsoleToolingHelper._DIFF_FLAGS}")
    print(
        f"diff flags for it    = "
        f"{ConsoleToolingHelper._DIFF_FLAGS.get(stripped_base)!r}"
    )
    print(f"uses_annotated_diff? = {_uses_annotated_diff_path(stripped)}")

    launcher = _simulated_gui_launcher(os.path.dirname(os.path.abspath(__file__)), 2)
    print("\n--- blocking behaviour (simulated 1s GUI launcher) ---")

    start = time.perf_counter()
    proc = subprocess.Popen([launcher], creationflags=CREATE_FLAGS)
    popen_return = time.perf_counter() - start
    proc.wait()
    print(f"Popen return only            = {popen_return * 1000:.2f}ms")

    start = time.perf_counter()
    _run_editor_process([launcher])
    sync_duration = time.perf_counter() - start
    print(f"_run_editor_process blocking = {sync_duration * 1000:.2f}ms")

    if sync_duration > popen_return * 20:
        print("\nRESULT: synchronous run blocks for the whole launcher duration;")
        print("background Popen returns immediately. Confirms the stutter mechanism.")
    else:
        print("\nRESULT: unexpected -- synchronous run did not block.")


if __name__ == "__main__":
    main()