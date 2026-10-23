"""Unit tests: the interruptible-call daemon-worker helper.

``run_interruptible`` runs a blocking callable on a daemon worker and returns
its result on the calling thread. The main thread polls the worker's future in
short slices, so a quit is handled within one slice instead of after the worker
returns. The worker is a daemon so a pending completion cannot block process
exit after a quit, and every worker failure is forwarded to the waiter
unchanged.
"""

import signal
import threading
import time

import pytest

from teddy_executor.core.utils.interrupt_guard import InterruptGuard, raise_interrupt
from teddy_executor.core.utils.interruptible_call import run_interruptible


class _BaseExceptionFailure(BaseException):
    """A BaseException subclass, so the test pins the deliberate catch-all."""


def test_returns_the_callable_result() -> None:
    expected = 42

    # Act
    result = run_interruptible(lambda: expected)

    # Assert
    assert result == expected


def test_runs_the_callable_off_the_calling_thread() -> None:
    observed: dict[str, int | None] = {}

    def _capture() -> str:
        observed["ident"] = threading.current_thread().ident
        return "done"

    caller_ident = threading.get_ident()

    # Act
    result = run_interruptible(_capture)

    # Assert: the blocking call must execute on a worker, not the caller.
    assert result == "done"
    assert observed["ident"] is not None, "the worker thread must carry an identifier"
    assert observed["ident"] != caller_ident


def test_the_worker_is_a_daemon_thread() -> None:
    observed: dict[str, bool] = {}

    def _capture() -> None:
        observed["daemon"] = threading.current_thread().daemon

    # Act
    run_interruptible(_capture)

    # Assert: a daemon worker cannot block process exit after a quit.
    assert observed["daemon"] is True


def test_forwards_worker_exceptions_unchanged() -> None:
    original = ValueError("worker failed")

    def _raise() -> None:
        raise original

    # Act / Assert: the waiter raises the very same exception instance.
    with pytest.raises(ValueError) as excinfo:
        run_interruptible(_raise)

    assert excinfo.value is original


def test_forwards_base_exceptions_unchanged() -> None:
    original = _BaseExceptionFailure("worker interrupted")

    def _raise() -> None:
        raise original

    # Act / Assert: a BaseException must reach the waiter, not hang it forever.
    with pytest.raises(_BaseExceptionFailure) as excinfo:
        run_interruptible(_raise)

    assert excinfo.value is original


def test_a_quit_wakes_the_waiter_before_the_worker_finishes() -> None:
    """A quit must interrupt the wait, not wait for the worker to finish."""
    fire_delay_seconds = 0.3
    worker_seconds = 3.0

    guard = InterruptGuard(monotonic=time.monotonic)
    previous = signal.signal(signal.SIGINT, guard._handle_signal)

    def _fire() -> None:
        time.sleep(fire_delay_seconds)
        guard.record_source("q")
        raise_interrupt()

    threading.Thread(target=_fire, daemon=True).start()
    started = time.perf_counter()
    try:
        with guard.enter_waiting():
            run_interruptible(lambda: time.sleep(worker_seconds))
    except KeyboardInterrupt:
        observed = time.perf_counter() - started
    else:
        pytest.fail("the quit did not interrupt the wait")
    finally:
        signal.signal(signal.SIGINT, previous)

    # A blocking wait would observe the quit only after the worker returns.
    assert observed < worker_seconds / 2
