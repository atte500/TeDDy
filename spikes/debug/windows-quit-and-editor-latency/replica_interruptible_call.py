"""Sandbox replica of the interruptible call with a polling wait.

The production ``run_interruptible`` blocks the main thread in
``future.result()``, which defers Windows SIGINT processing until the worker
completes. This replica polls the future in short slices so the main thread
keeps executing bytecode and a pending interrupt is raised promptly.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import TypeVar

T = TypeVar("T")

# How long each poll slice waits before the main thread yields to signals.
_POLL_SECONDS = 0.05


def run_interruptible(func: Callable[[], T]) -> T:
    """Run ``func`` on a daemon worker, polling so a quit wakes the waiter."""
    future: Future[T] = Future()

    def _work() -> None:
        try:
            future.set_result(func())
        except BaseException as exc:  # forward every failure to the waiter
            future.set_exception(exc)

    worker = threading.Thread(target=_work, name="interruptible-call", daemon=True)
    worker.start()
    while True:
        try:
            return future.result(timeout=_POLL_SECONDS)
        except FutureTimeoutError:
            continue