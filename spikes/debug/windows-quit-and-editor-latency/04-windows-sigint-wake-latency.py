"""Measure how quickly a self-delivered SIGINT wakes the planning wait.

The quit-key listener runs on a reader thread and calls ``raise_interrupt``
while the main thread waits on the planning completion. This spike records the
observed latency for the shipped blocking wait, a main-thread polling control,
and a future-polling candidate. It needs no console and finishes in seconds.
"""

from __future__ import annotations

import signal
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from teddy_executor.core.utils.interrupt_guard import InterruptGuard, raise_interrupt
from teddy_executor.core.utils.interruptible_call import run_interruptible

# The fake quit fires well before the worker finishes, so a deferred delivery
# is visible as a latency close to the worker duration instead of the fire delay.
FIRE_DELAY_SECONDS = 0.3
WORK_SECONDS = 1.5
POLL_SECONDS = 0.05


def _install_firing_guard() -> tuple[InterruptGuard, Any, threading.Thread]:
    """Install the guard and start a worker that fires the quit after a delay."""
    guard = InterruptGuard(monotonic=time.monotonic)
    previous = guard.install()

    def fire() -> None:
        time.sleep(FIRE_DELAY_SECONDS)
        guard.record_source("q")
        raise_interrupt()

    thread = threading.Thread(target=fire, name="probe-fire", daemon=True)
    thread.start()
    return guard, previous, thread


def _sleep_polling(seconds: float) -> None:
    """Wait in short slices so the main thread keeps executing bytecode."""
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        time.sleep(0.01)


def _run_future_polling(func: Callable[[], Any], poll: float) -> Any:
    """Run the callable on a worker and wait in slices so signals are processed."""
    future: Future = Future()

    def work() -> None:
        try:
            future.set_result(func())
        except BaseException as exc:  # forward every failure to the waiter
            future.set_exception(exc)

    threading.Thread(target=work, name="probe-worker", daemon=True).start()
    while True:
        try:
            return future.result(timeout=poll)
        except FutureTimeoutError:
            continue


def _measure(label: str, wait: Callable[[], Any]) -> dict[str, object]:
    """Run one wait scenario and report its outcome and wake latency."""
    guard, previous, firing = _install_firing_guard()
    started = time.perf_counter()
    outcome = "completed"
    try:
        try:
            with guard.enter_waiting():
                wait()
        except KeyboardInterrupt:
            outcome = "interrupted"
        finally:
            signal.signal(signal.SIGINT, previous)
    except KeyboardInterrupt:
        outcome = "interrupted-after-finally"
    firing.join(timeout=2.0)
    return {
        "scenario": label,
        "outcome": outcome,
        "latency_s": round(time.perf_counter() - started, 3),
        "fire_at_s": FIRE_DELAY_SECONDS,
        "work_s": WORK_SECONDS,
        "source": guard.source,
    }


def main() -> int:
    """Run the blocking, control, and candidate scenarios in order."""
    print(f"platform={sys.platform} python={sys.version.split()[0]}", flush=True)
    scenarios: list[tuple[str, Callable[[], Any]]] = [
        (
            "blocking_future_result",
            lambda: run_interruptible(lambda: time.sleep(WORK_SECONDS)),
        ),
        ("main_thread_polling_control", lambda: _sleep_polling(WORK_SECONDS)),
        (
            "future_polling_candidate",
            lambda: _run_future_polling(
                lambda: time.sleep(WORK_SECONDS), POLL_SECONDS
            ),
        ),
    ]
    for label, wait in scenarios:
        print(dict(_measure(label, wait)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())