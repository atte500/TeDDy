"""Probe: attribute the Windows-only editor-open stutter to a specific stage.

Times the synchronous work the Textual event loop performs before
``spawn_editor`` returns control: editor resolution (PATH scan), temp-file
staging, and the ``.cmd`` spawn through ``cmd.exe``. Uses a no-op batch file
so the real GUI editor is launched only once, at the end, and then terminated.
"""

from __future__ import annotations

import os
import statistics
import subprocess
import sys
import time
from typing import Any, Callable, Optional


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


def _timeit(fn: Callable[[], Any], n: int = 15) -> tuple[Any, list[float]]:
    samples: list[float] = []
    result: Any = None
    for _ in range(n):
        start = time.perf_counter()
        result = fn()
        samples.append(time.perf_counter() - start)
    return result, samples


def _fmt(samples: list[float]) -> str:
    ms = [s * 1000 for s in samples]
    return (
        f"median={statistics.median(ms):-.2f}ms "
        f"min={min(ms):.2f}ms max={max(ms):.2f}ms n={len(ms)}"
    )


def _spawn_return_latency(cmd: list[str], terminate: bool) -> float:
    start = time.perf_counter()
    proc = subprocess.Popen(cmd, creationflags=CREATE_FLAGS)
    elapsed = time.perf_counter() - start
    if terminate:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            pass
    return elapsed


def main() -> None:
    print(f"platform={sys.platform} python={sys.version.split()[0]}")

    env = SystemEnvironmentAdapter()
    cfg = _ConfigStub({"editor": "codium"})
    tooling = ConsoleToolingHelper(env, cfg)

    resolved = env.which("codium")
    print(f"\nresolved codium = {resolved!r}")
    _, which_samples = _timeit(lambda: env.which("codium"))
    print(f"which('codium')             {_fmt(which_samples)}")

    editor_cmd, find_samples = _timeit(tooling.find_editor)
    print(f"find_editor()               {_fmt(find_samples)}  -> {editor_cmd!r}")

    diff_cmd, diff_samples = _timeit(tooling.get_diff_viewer_command)
    print(f"get_diff_viewer_command()   {_fmt(diff_samples)}  -> {diff_cmd!r}")

    def make_temp() -> str:
        path = env.create_temp_file(suffix=".md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("# probe\n" * 50)
        os.chmod(path, 0o644)
        return path

    temp_path, temp_samples = _timeit(make_temp)
    print(f"create+write+chmod          {_fmt(temp_samples)}")

    noop_cmd = os.path.join(os.path.dirname(__file__), "noop.cmd")
    _, return_only = _timeit(lambda: _spawn_return_latency([noop_cmd], True))
    print(f"Popen(noop.cmd) return only {_fmt(return_only)}")

    def popen_and_wait() -> None:
        proc = subprocess.Popen([noop_cmd], creationflags=CREATE_FLAGS)
        proc.wait()

    _, full_run = _timeit(popen_and_wait)
    print(f"Popen(noop.cmd)+wait        {_fmt(full_run)}")

    if resolved:
        latency = _spawn_return_latency([resolved, temp_path], terminate=True)
        print(f"\nPopen(codium.cmd) return    {latency * 1000:.2f}ms (single shot)")
        env.delete_file(temp_path)

    print("\ndone")


if __name__ == "__main__":
    main()