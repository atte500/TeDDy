"""Unit tests: the interruptible-call daemon-worker helper.

``run_interruptible`` runs a blocking callable on a daemon worker and returns
its result on the calling thread. The planning completion blocks the main
thread inside a raw socket read, which the Windows CRT raise cannot wake.
Moving the call to a daemon worker keeps the main thread in a condition wait,
which every SIGINT delivery primitive wakes immediately. The worker is a daemon
so a pending completion cannot block process exit after a quit, and every
worker failure is forwarded to the waiter unchanged.
"""

import threading

import pytest

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
