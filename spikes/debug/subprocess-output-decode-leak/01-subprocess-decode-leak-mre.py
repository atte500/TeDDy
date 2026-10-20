"""MRE: the ShellAdapter subprocess text-mode decode leak.

Drives the production ShellAdapter against a child that emits a byte
undefined in cp1252 and invalid as a UTF-8 start byte. Captures the
reader-thread exception in-process and prints the resulting payload.
"""

import sys
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter

HELPER = Path(__file__).resolve().with_name("emit_invalid_byte.py")


def main() -> int:
    leaks: list[BaseException] = []

    def _hook(args: "threading.ExceptHookArgs") -> None:
        leaks.append(args.exc_value)

    threading.excepthook = _hook

    adapter = ShellAdapter(max_execute_lines=1000)
    command = f'"{sys.executable}" "{HELPER}"'

    kwargs = adapter._prepare_subprocess_kwargs(
        use_shell=False, cwd=str(HELPER.parent), env={}
    )
    print("subprocess kwargs keys:", sorted(kwargs))
    print("explicit encoding:", kwargs.get("encoding"))
    print("errors policy:", kwargs.get("errors"))
    print("text mode:", kwargs.get("text"))

    result = adapter.execute(command, cwd=str(HELPER.parent))

    print("\n--- adapter result ---")
    print("stdout repr:", repr(result.get("stdout")))
    print("stderr repr:", repr(result.get("stderr")))
    print("return_code:", result.get("return_code"))

    print("\n--- reader-thread exceptions ---")
    if not leaks:
        print("none")
    for exc in leaks:
        print(type(exc).__name__ + ":", exc)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())