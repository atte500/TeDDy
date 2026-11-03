"""MRE: EXECUTE timeout output is returned untruncated.

Drives the real ``ShellAdapter`` (imported from ``src/``) into its timeout
path by mocking only the subprocess boundary. The fake process raises
``TimeoutExpired`` on the first ``communicate`` (the wait) and then yields a
large partial payload on the second call (gathered inside ``_handle_timeout``).

Expected behaviour: stdout is capped to ``max_execute_lines`` with a tail
truncation hint. Observed behaviour: the full payload is returned, so the
script exits non-zero with "BUG REPRODUCED".
"""

import subprocess

from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter


class _TimedOutProcess:
    """Fake Popen: times out once, then yields large partial output."""

    def __init__(self, partial_stdout: str) -> None:
        self.pid = 999999  # Non-existent PID; os.killpg raises OSError, which is swallowed.
        self.returncode = None
        self._partial_stdout = partial_stdout
        self._calls = 0

    def communicate(self, timeout=None):
        self._calls += 1
        if self._calls == 1:
            raise subprocess.TimeoutExpired(cmd="slow", timeout=timeout)
        return (self._partial_stdout, "boom stderr")

    def kill(self) -> None:  # pragma: no cover - not reached on POSIX path
        pass


def main() -> int:
    max_lines = 5
    partial = "\n".join(f"line{i}" for i in range(1, 201))

    adapter = ShellAdapter(max_execute_lines=max_lines)
    process = _TimedOutProcess(partial)
    adapter._popen = lambda *args, **kwargs: process  # type: ignore[assignment]

    result = adapter.execute("slow-command", timeout=0.1)
    stdout = result["stdout"]
    lines = stdout.splitlines()

    print(f"return_code={result['return_code']}")
    print(f"stdout_lines={len(lines)}")

    assert result["return_code"] == ShellAdapter.TIMEOUT_EXIT_CODE
    assert "[ERROR: Command timed out" in stdout

    if len(lines) > max_lines + 2:  # warning + hint + max_lines is the correct ceiling
        print("BUG REPRODUCED: timeout output was not truncated")
        return 1

    print("OK: timeout output truncated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())