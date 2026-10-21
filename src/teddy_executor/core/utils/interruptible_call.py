"""Run a blocking callable on a daemon worker so a quit can wake the waiter.

The planning completion blocks the main thread inside a raw socket read. A
POSIX signal reaches that call only through a main-thread target, and the
Windows CRT raise cannot wake it at all. Running the call on a daemon worker
keeps the main thread in a condition wait, which every SIGINT delivery
primitive wakes immediately.

The worker is a daemon so a pending completion cannot block process exit after
a quit. Every worker failure is forwarded to the waiter unchanged.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import Future
from typing import TypeVar

T = TypeVar("T")


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
    return future.result()
