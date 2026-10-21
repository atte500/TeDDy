"""MRE: quit-key SIGINT delivery latency.

A worker thread delivers SIGINT after a fixed delay while the main thread
blocks in a C-level wait. The probe reports the time between delivery and the
Python handler for each strategy. ``raise_signal`` mimics the production quit
path. ``main_thread_kill`` and the replica carry the proposed fix.
"""

import os
import select
import signal
import sys
import threading
import time

from replica_interrupt_guard import raise_interrupt as replica_raise_interrupt

DELIVERY_THRESHOLD_SECONDS = 0.2
BOUNDED_WAIT_SECONDS = 1.0
LONG_WAIT_SECONDS = 3.0

_handler_at: list[float] = []
_delivered_at: list[float] = []


def _handler(signum: int, frame: object) -> None:
    _handler_at.append(time.monotonic())
    raise KeyboardInterrupt


def _deliver(mode: str) -> None:
    time.sleep(DELIVERY_THRESHOLD_SECONDS)
    _delivered_at.append(time.monotonic())
    if mode == "raise_signal":
        signal.raise_signal(signal.SIGINT)
    elif mode == "process_kill":
        os.kill(os.getpid(), signal.SIGINT)
    elif mode == "main_thread_kill":
        signal.pthread_kill(threading.main_thread().ident, signal.SIGINT)
    elif mode == "replica":
        replica_raise_interrupt()
    else:
        raise SystemExit(f"unknown mode: {mode}")


def _wait(scenario: str) -> None:
    if scenario == "bounded_wait":
        select.select([], [], [], BOUNDED_WAIT_SECONDS)
    elif scenario == "long_wait":
        time.sleep(LONG_WAIT_SECONDS)
    else:
        raise SystemExit(f"unknown scenario: {scenario}")


def _run(mode: str, scenario: str) -> None:
    _handler_at.clear()
    _delivered_at.clear()
    previous = signal.signal(signal.SIGINT, _handler)
    try:
        worker = threading.Thread(target=_deliver, args=(mode,), daemon=True)
        worker.start()
        try:
            _wait(scenario)
            outcome = "no-interrupt"
        except KeyboardInterrupt:
            outcome = "interrupted"
        latency = (
            round(_handler_at[0] - _delivered_at[0], 3)
            if _handler_at and _delivered_at
            else None
        )
        print(
            f"mode={mode:<18} scenario={scenario:<13} "
            f"outcome={outcome:<14} latency={latency}"
        )
    finally:
        signal.signal(signal.SIGINT, previous)


def main() -> None:
    print(f"platform={sys.platform} python={sys.version.split()[0]}")
    for scenario in ("bounded_wait", "long_wait"):
        for mode in ("raise_signal", "process_kill", "main_thread_kill", "replica"):
            _run(mode, scenario)


if __name__ == "__main__":
    main()