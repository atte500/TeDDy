"""Run a blocking callable on a daemon worker so a quit can wake the waiter.

The planning completion blocks the main thread inside a raw socket read. A
POSIX signal reaches that call only through a main-thread target, and the
Windows CRT raise cannot wake it at all. Running the call on a daemon worker
moves the wait into a future the main thread polls in short slices.

Polling matters on Windows: a single blocking ``Future.result()`` runs no
bytecode, so the CRT defers a pending SIGINT flag until the worker returns and
the user perceives a missed quit key. A poll slice returns to the bytecode
loop, so the installed handler runs within one slice.

The worker is a daemon so a pending completion cannot block process exit after
a quit. Every worker failure is forwarded to the waiter unchanged.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import TypeVar

T = TypeVar("T")

# How long one wait slice blocks before the main thread yields to signals.
_POLL_SECONDS = 0.05


def run_interruptible(func: Callable[[], T]) -> T:
    """Run ``func`` on a daemon worker and return its result or raise its error."""
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
