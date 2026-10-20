"""Verify the decode-policy fix against the sandbox replica.

Runs the same two child payloads through the production adapter and the
replica, capturing reader-thread exceptions in-process, so the proof is
side-by-side evidence rather than a claim.
"""

import importlib.util
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from teddy_executor.adapters.outbound.shell_adapter import (  # noqa: E402
    ShellAdapter as ProductionShellAdapter,
)

CASES = [
    ("valid-utf8", "emit_utf8_emoji.py"),
    ("invalid-byte", "emit_invalid_byte.py"),
]


def _load_replica_adapter():
    spec = importlib.util.spec_from_file_location(
        "replica_shell_adapter", HERE / "replica_shell_adapter.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ShellAdapter


def _run_case(adapter_cls, helper: Path) -> tuple[dict, list[BaseException]]:
    leaks: list[BaseException] = []
    previous = threading.excepthook

    def _hook(args):
        leaks.append(args.exc_value)

    threading.excepthook = _hook
    try:
        adapter = adapter_cls(max_execute_lines=1000)
        result = adapter.execute(f'"{sys.executable}" "{helper}"', cwd=str(HERE))
    finally:
        threading.excepthook = previous
    return result, leaks


def main() -> int:
    replica_adapter = _load_replica_adapter()
    for label, helper_name in CASES:
        helper = HERE / helper_name
        for name, adapter_cls in (
            ("production", ProductionShellAdapter),
            ("replica", replica_adapter),
        ):
            result, leaks = _run_case(adapter_cls, helper)
            print(f"[{label}] {name}")
            print(f"  stdout: {ascii(result.get('stdout'))}")
            print(f"  stderr: {ascii(result.get('stderr'))}")
            print(f"  return_code: {result.get('return_code')}")
            print(f"  reader-thread exceptions: {[type(e).__name__ for e in leaks]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())