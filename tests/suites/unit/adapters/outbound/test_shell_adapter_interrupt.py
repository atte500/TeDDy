"""Unit tests: ShellAdapter in-flight interrupt termination (Bug 58 Option B).

When the process-global InterruptGuard's drain flag is set while a command is
running, the adapter must terminate the child's ISOLATED process group (the
child runs in its own session via ``os.setsid()``) and return a ShellOutput
marked ``interrupted=True`` with the partial output.
"""

import os
import signal
import time

from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter
from teddy_executor.core.utils.interrupt_guard import InterruptGuard


class _FakeProcess:
    """Hand-rolled Popen double: records communicate/kill (not a mock)."""

    def __init__(self, partial: str = "partial output") -> None:
        self.pid = 4242
        self.args = ["sleep", "30"]
        self.returncode = -9
        self._partial = partial
        self.communicate_calls = 0

    def communicate(self, timeout=None):  # noqa: ARG002
        self.communicate_calls += 1
        return (self._partial, "")

    def kill(self) -> None:  # pragma: no cover - fallback path
        pass


def _real_guard() -> InterruptGuard:
    return InterruptGuard(monotonic=time.monotonic)


def test_await_process_terminates_group_and_reports_interrupt(monkeypatch):
    guard = _real_guard()
    guard.interrupted.set()

    killed: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "killpg", lambda pid, sig: killed.append((pid, sig)))

    adapter = ShellAdapter(interrupt_guard=guard)
    process = _FakeProcess()

    stdout, stderr, interrupted = adapter._await_process(process, timeout=30.0)

    assert interrupted is True
    assert killed == [(process.pid, signal.SIGKILL)]
    assert (stdout, stderr) == ("partial output", "")


def test_await_process_without_guard_is_single_blocking_communicate():
    adapter = ShellAdapter()  # no guard -> legacy behaviour
    process = _FakeProcess(partial="done")

    stdout, stderr, interrupted = adapter._await_process(process, timeout=30.0)

    assert interrupted is False
    assert (stdout, stderr) == ("done", "")
    assert process.communicate_calls == 1
