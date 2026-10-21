"""Remote probe: cross-platform SIGINT delivery latency.

Production delivers the bare-`q` interrupt with ``signal.raise_signal`` from the
quit-key reader thread. This probe measures how quickly the Python handler runs
while the main thread blocks in a realistic wait, for the current primitive and
for the candidate replacements.

The probe reports the thread that ran the handler, so a thread-directed
delivery is visible in the output. ``os.kill(getpid, SIGINT)`` is skipped on
Windows because that call terminates the process there. One extra Windows mode
cancels the main thread's pending synchronous I/O before raising, which tests
whether a blocking socket read can be woken at all. An unbounded future wait is
measured with a safety release, because a shipped runner would use no timeout.
"""

from __future__ import annotations

import _thread
import os
import signal
import socket
import sys
import threading
import time

from concurrent.futures import Future

DELIVERY_DELAY_SECONDS = 0.2
WORKER_JOIN_TIMEOUT_SECONDS = 5.0
UNBOUNDED_SAFETY_SECONDS = 5.0

WAITS = (
    "sleep_1s",
    "sleep_3s",
    "socket_1s",
    "future_1s",
    "event_1s",
    "future_unbounded",
)


def _replica_raise_interrupt() -> None:
    """Deliver SIGINT to the main thread on POSIX, or via the CRT on Windows."""
    if sys.platform != "win32" and hasattr(signal, "pthread_kill"):
        main_ident = threading.main_thread().ident
        if main_ident is not None:
            signal.pthread_kill(main_ident, signal.SIGINT)
            return
    signal.raise_signal(signal.SIGINT)


_DELIVERY_NOTES: list[str] = []


def _cancel_synchronous_io(thread_ident: int | None) -> None:
    """Cancel the main thread's pending synchronous I/O (Windows only).

    A blocking ``recv`` is not an alertable wait, so the pending Python signal
    call cannot run until the read returns. Cancelling the read forces an
    immediate return and therefore an immediate handler checkpoint.
    """
    if thread_ident is None:
        raise OSError("main thread ident is unavailable")
    import ctypes  # noqa: PLC0415
    from ctypes import wintypes  # noqa: PLC0415

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenThread.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CancelSynchronousIo.argtypes = [wintypes.HANDLE]
    kernel32.CancelSynchronousIo.restype = wintypes.BOOL
    thread_terminate = 0x0001
    handle = kernel32.OpenThread(thread_terminate, False, thread_ident)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not kernel32.CancelSynchronousIo(handle):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel32.CloseHandle(handle)


def _deliver(mode: str) -> None:
    if mode == "raise_signal_current":
        signal.raise_signal(signal.SIGINT)
    elif mode == "replica":
        _replica_raise_interrupt()
    elif mode == "process_kill":
        os.kill(os.getpid(), signal.SIGINT)
    elif mode == "main_thread_kill":
        signal.pthread_kill(threading.main_thread().ident, signal.SIGINT)
    elif mode == "interrupt_main":
        _thread.interrupt_main()
    elif mode == "cancel_sync_io_then_raise":
        try:
            _cancel_synchronous_io(threading.main_thread().ident)
        except OSError as exc:
            _DELIVERY_NOTES.append(str(exc))
        signal.raise_signal(signal.SIGINT)
    else:
        raise SystemExit(f"unknown mode: {mode}")


def _block_main(wait: str) -> None:
    """Block the main thread the way the production loop can be blocked."""
    if wait == "sleep_1s":
        time.sleep(1.0)
    elif wait == "sleep_3s":
        time.sleep(3.0)
    elif wait == "socket_1s":
        reader, writer = socket.socketpair()
        try:
            reader.settimeout(1.0)
            try:
                reader.recv(1)
            except (TimeoutError, OSError):
                pass
        finally:
            reader.close()
            writer.close()
    elif wait == "future_1s":
        # Mirrors a sliced ``future.result(timeout=...)`` wait: the main thread
        # blocks on the future's condition lock, the shape a polled LLM wait uses.
        pending: Future[str] = Future()
        try:
            pending.result(timeout=1.0)
        except TimeoutError:
            pass
    elif wait == "event_1s":
        threading.Event().wait(1.0)
    elif wait == "future_unbounded":
        # Mirrors an unbounded ``future.result()`` wait: the shape a runner
        # uses when it waits on a completion worker. The safety timer releases
        # the wait if the delivery primitive cannot wake it, so the probe
        # reports a latency instead of hanging.
        pending: Future[str] = Future()

        def _release() -> None:
            if not pending.done():
                pending.set_result("released")

        safety = threading.Timer(UNBOUNDED_SAFETY_SECONDS, _release)
        safety.daemon = True
        safety.start()
        try:
            pending.result()
        finally:
            safety.cancel()
    else:
        raise SystemExit(f"unknown wait: {wait}")


def _run(mode: str, wait: str) -> None:
    handler_at: list[float] = []
    delivered_at: list[float] = []
    handler_thread: list[str] = []
    delivery_errors: list[str] = []
    interrupt_at: list[float] = []

    def handler(signum: int, frame: object) -> None:
        if not handler_at:
            handler_at.append(time.monotonic())
            handler_thread.append(
                "main"
                if threading.current_thread() is threading.main_thread()
                else threading.current_thread().name
            )
        raise KeyboardInterrupt

    def deliver() -> None:
        time.sleep(DELIVERY_DELAY_SECONDS)
        delivered_at.append(time.monotonic())
        try:
            _deliver(mode)
        except BaseException as exc:  # diagnostic probe: record, never mask
            delivery_errors.append(type(exc).__name__)

    _DELIVERY_NOTES.clear()
    previous = signal.signal(signal.SIGINT, handler)
    interrupted = False
    worker = threading.Thread(target=deliver, daemon=True)
    try:
        worker.start()
        try:
            _block_main(wait)
            worker.join(timeout=WORKER_JOIN_TIMEOUT_SECONDS)
        except KeyboardInterrupt:
            # The handler can also fire at the first checkpoint AFTER the
            # blocking call returns, so the guard spans the join as well.
            interrupted = True
            interrupt_at.append(time.monotonic())
    finally:
        signal.signal(signal.SIGINT, previous)

    handler_ms = (
        round((handler_at[0] - delivered_at[0]) * 1000)
        if handler_at and delivered_at
        else None
    )
    interrupt_ms = (
        round((interrupt_at[0] - delivered_at[0]) * 1000)
        if interrupt_at and delivered_at
        else None
    )
    thread_label = handler_thread[0] if handler_thread else "none"
    print(
        f"mode={mode:<26} wait={wait:<17} "
        f"handler_thread={thread_label:<12} handler_ms={handler_ms} "
        f"interrupt_ms={interrupt_ms} interrupted={interrupted} "
        f"delivery_error={delivery_errors or 'none'} "
        f"delivery_note={_DELIVERY_NOTES or 'none'}"
    )
    sys.stdout.flush()


def main() -> None:
    print(f"platform={sys.platform} python={sys.version.split()[0]}")
    print(
        f"pthread_kill={hasattr(signal, 'pthread_kill')} "
        f"main_ident={threading.main_thread().ident}"
    )
    modes = ["raise_signal_current", "replica", "interrupt_main"]
    if sys.platform == "win32":
        modes.append("cancel_sync_io_then_raise")
    if sys.platform != "win32":
        modes.append("process_kill")
    if hasattr(signal, "pthread_kill"):
        modes.append("main_thread_kill")
    for wait in WAITS:
        for mode in modes:
            _run(mode, wait)


if __name__ == "__main__":
    main()