"""Baseline timings for the Windows test-suite slowness investigation.

Measures the work every pytest-xdist worker repeats at startup: cold imports
of the heavy dependency stack, the session-scoped git status shell-out, the
per-test project-root lookup, and the pyfakefs patch cycle cost.
"""

import os
import platform
import subprocess
import sys
import time
from pathlib import Path

HEAVY_MODULES = ("pytest", "litellm", "trafilatura", "textual", "ddgs", "mistletoe")


def measure(label: str, function) -> float:
    start = time.perf_counter()
    function()
    duration = time.perf_counter() - start
    print(f"{label}: {duration:.3f}s")
    return duration


def import_module(module_name: str) -> None:
    __import__(module_name)


def git_status() -> None:
    subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        timeout=60,
    )


def main() -> None:
    print(f"python: {sys.version.split()[0]}")
    print(f"platform: {platform.platform()}")
    print(f"cpu_count: {os.cpu_count()}")

    for module_name in HEAVY_MODULES:
        measure(f"cold import {module_name}", lambda name=module_name: import_module(name))

    sys.path.insert(0, str(Path("src").resolve()))
    from teddy_executor.adapters.inbound.cli_helpers import find_project_root

    measure("find_project_root x100", lambda: [find_project_root() for _ in range(100)])
    measure("git status --porcelain (1)", git_status)
    measure("git status --porcelain (2)", git_status)
    measure("git status --porcelain (3)", git_status)

    def fakefs_cycle() -> None:
        from pyfakefs.fake_filesystem_unittest import Patcher

        patcher = Patcher()
        patcher.setUp()
        try:
            Path("probe.txt").write_text("x")
        finally:
            patcher.tearDown()

    try:
        measure("pyfakefs patch cycle", fakefs_cycle)
    except (ImportError, RuntimeError) as error:
        print(f"pyfakefs patch cycle: unavailable ({error})")


if __name__ == "__main__":
    main()