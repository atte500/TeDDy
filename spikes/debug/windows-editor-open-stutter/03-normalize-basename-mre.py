"""Probe: prove the shared basename normalization fixes Windows editor routing.

Loads the sandbox replica of the faulty editor module and asserts that
stripping the Windows launcher suffix (``.CMD``) restores correct
classification: codium is a GUI editor routed to the non-blocking before/after
diff flow, and a terminal editor wrapper such as ``nvim.CMD`` is classified as
a CLI editor. The replica is built by ``build_replica.py`` with the proposed
fix applied.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import time
from typing import Any


def _bootstrap() -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    src = os.path.join(root, "src")
    if src not in sys.path:
        sys.path.insert(0, src)


_bootstrap()

from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
from teddy_executor.adapters.outbound.system_environment_adapter import (
    SystemEnvironmentAdapter,
)


class _ConfigStub:
    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)


def _load_replica() -> Any:
    path = os.path.join(
        os.path.dirname(__file__), "replica_textual_plan_reviewer_editor.py"
    )
    spec = importlib.util.spec_from_file_location("replica_editor", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    replica = _load_replica()
    env = SystemEnvironmentAdapter()
    tooling = ConsoleToolingHelper(env, _ConfigStub({"editor": "codium"}))

    real_cmd = tooling.find_editor()
    assert real_cmd, "codium must resolve for this probe"
    real_name = os.path.basename(real_cmd[0])
    print(f"resolved editor = {real_cmd[0]!r}")

    nvim_wrapper = [os.path.join(os.path.dirname(real_cmd[0]), "nvim.CMD")]

    failures: list[str] = []

    print("\n--- codium (GUI) routing after normalization ---")
    annotated = replica._uses_annotated_diff_path(real_cmd)
    cli = replica._is_cli_editor(real_cmd)
    print(f"basename                    = {real_name!r}")
    print(f"_uses_annotated_diff_path   = {annotated} (expected False)")
    print(f"_is_cli_editor              = {cli} (expected False)")
    if annotated is not False:
        failures.append("codium routed to the blocking annotated diff path")
    if cli is not False:
        failures.append("codium misclassified as a CLI editor")

    print("\n--- nvim wrapper (CLI) routing after normalization ---")
    cli_v = replica._is_cli_editor(nvim_wrapper)
    vim_v = replica._is_vim_editor(nvim_wrapper)
    annotated_v = replica._uses_annotated_diff_path(nvim_wrapper)
    print(f"basename                    = {os.path.basename(nvim_wrapper[0])!r}")
    print(f"_is_cli_editor              = {cli_v} (expected True)")
    print(f"_is_vim_editor              = {vim_v} (expected True)")
    print(f"_uses_annotated_diff_path   = {annotated_v} (expected True)")
    if cli_v is not True:
        failures.append("nvim wrapper misclassified as GUI")
    if vim_v is not True:
        failures.append("nvim wrapper not detected as vim")
    if annotated_v is not True:
        failures.append("nvim wrapper not routed to the annotated flow")

    slowgui = os.path.join(os.path.dirname(__file__), "slowgui.cmd")
    if os.path.exists(slowgui):
        print("\n--- non-blocking background launch (the path the fix selects) ---")
        start = time.perf_counter()
        env.run_command([slowgui], background=True)
        bg_return = (time.perf_counter() - start) * 1000
        print(f"background run_command return = {bg_return:.2f}ms (expected <300ms)")
        if bg_return > 300:
            failures.append("background launch unexpectedly blocked")

    if failures:
        print("\nRESULT: RED -- replica still shows the bug:")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("\nRESULT: GREEN -- normalization routes codium to the non-blocking flow.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())