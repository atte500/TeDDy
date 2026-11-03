"""Verify the replica fix: EXECUTE timeout output is truncated.

Imports the fixed replica of ``ShellAdapter`` and drives the same timeout
scenario as the MRE. Exits 0 only when both the default cap and a per-call
``max_lines`` override produce a capped body with the warning and the
tail-truncation hint present.
"""

import subprocess

from replica_shell_adapter import ShellAdapter


class _TimedOutProcess:
    """Fake Popen: times out once, then yields large partial output."""

    def __init__(self, partial_stdout: str) -> None:
        self.pid = 999999  # Non-existent PID; os.killpg raises OSError, swallowed.
        self.returncode = None
        self._partial_stdout = partial_stdout
        self._calls = 0

    def communicate(self, timeout=None):
        self._calls += 1
        if self._calls == 1:
            raise subprocess.TimeoutExpired(cmd="slow", timeout=timeout)
        return (self._partial_stdout, "boom stderr")

    def kill(self) -> None:  # pragma: no cover - POSIX path swallows OSError
        pass


def _run(adapter_default: int, call_max_lines: int | None, payload_lines: int):
    partial = "\n".join(f"line{i}" for i in range(1, payload_lines + 1))
    adapter = ShellAdapter(max_execute_lines=adapter_default)
    process = _TimedOutProcess(partial)
    adapter._popen = lambda *args, **kwargs: process  # type: ignore[assignment]
    kwargs = {"timeout": 0.1}
    if call_max_lines is not None:
        kwargs["max_lines"] = call_max_lines
    return adapter.execute("slow-command", **kwargs)


def _check(label: str, result, expected_cap: int, payload_lines: int) -> bool:
    stdout = result["stdout"]
    lines = stdout.splitlines()
    ceiling = expected_cap + 2  # warning + hint + capped body
    expect_hint = payload_lines > expected_cap
    print(f"[{label}] return_code={result['return_code']} stdout_lines={len(lines)}")
    print(stdout)
    print("-" * 40)

    ok = True
    if result["return_code"] != ShellAdapter.TIMEOUT_EXIT_CODE:
        print(f"FAIL[{label}]: wrong return code")
        ok = False
    if "[ERROR: Command timed out" not in stdout:
        print(f"FAIL[{label}]: missing timeout warning")
        ok = False
    if expect_hint and "[Output truncated" not in stdout:
        print(f"FAIL[{label}]: missing tail-truncation hint")
        ok = False
    if not expect_hint and "[Output truncated" in stdout:
        print(f"FAIL[{label}]: unexpected truncation hint on short/empty output")
        ok = False
    if len(lines) > ceiling:
        print(f"FAIL[{label}]: body not capped ({len(lines)} > {ceiling})")
        ok = False
    return ok


def main() -> int:
    results = [
        ("default-cap", _run(adapter_default=5, call_max_lines=None, payload_lines=200), 5, 200),
        ("override", _run(adapter_default=100, call_max_lines=3, payload_lines=200), 3, 200),
        ("no-output", _run(adapter_default=5, call_max_lines=None, payload_lines=0), 5, 0),
    ]
    ok = all(_check(label, result, cap, payload) for label, result, cap, payload in results)
    if not ok:
        print("VERIFICATION FAILED")
        return 1
    print("OK: timeout output truncated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())