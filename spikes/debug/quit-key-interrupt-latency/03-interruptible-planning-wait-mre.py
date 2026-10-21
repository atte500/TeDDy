"""MRE: the one-slice interruptible planning wait.

Production planning blocks the main thread inside the LLM socket read. The
proposed slice runs that call on a worker and waits on its future, keeping the
main thread in a condition wait. A third thread simulates the quit-key reader
delivering SIGINT, so this MRE measures the whole topology instead of a bare
future wait.
"""

from __future__ import annotations

import os
import signal
import socket
import sys
import threading
import time

from replica_interrupt_guard import raise_interrupt as replica_raise_interrupt
from replica_interruptible_call import run_interruptible

DELIVERY_DELAY_SECONDS = 0.2
LLM_RESPONSE_SECONDS = 2.0


def _llm_style_read(reader: socket.socket) -> str:
    """Block in a raw socket read, the shape of an in-flight LLM response."""
    try:
        reader.recv(1)
    except OSError:
        pass
    return "response"


def _deliver(mode: str, delivered_at: list[float]) -> None:
    time.sleep(DELIVERY_DELAY_SECONDS)
    delivered_at.append(time.monotonic())
    if mode == "raise_signal":
        signal.raise_signal(signal.SIGINT)
    elif mode == "process_kill":
        os.kill(os.getpid(), signal.SIGINT)
    elif mode == "replica":
        replica_raise_interrupt()
    else:
        raise SystemExit(f"unknown mode: {mode}")


def _run(mode: str) -> None:
    handler_at: list[float] = []
    handler_thread: list[str] = []
    delivered_at: list[float] = []

    def handler(signum: int, frame: object) -> None:
        if not handler_at:
            handler_at.append(time.monotonic())
            handler_thread.append(
                "main"
                if threading.current_thread() is threading.main_thread()
                else threading.current_thread().name
            )
        raise KeyboardInterrupt

    reader, writer = socket.socketpair()
    reader.settimeout(LLM_RESPONSE_SECONDS)
    previous = signal.signal(signal.SIGINT, handler)
    interrupted = False
    try:
        threading.Thread(
            target=_deliver, args=(mode, delivered_at), daemon=True
        ).start()
        try:
            run_interruptible(lambda: _llm_style_read(reader))
        except KeyboardInterrupt:
            interrupted = True
    finally:
        signal.signal(signal.SIGINT, previous)
        writer.close()
        reader.close()

    latency_ms = (
        round((handler_at[0] - delivered_at[0]) * 1000)
        if handler_at and delivered_at
        else None
    )
    thread_label = handler_thread[0] if handler_thread else "none"
    print(
        f"mode={mode:<14} handler_thread={thread_label:<5} "
        f"latency_ms={latency_ms} interrupted={interrupted}"
    )
    sys.stdout.flush()


def _modes() -> tuple[str, ...]:
    """List the delivery modes that are safe on this platform.

    ``os.kill`` terminates the process on Windows, so that mode is skipped
    there and the CRT raise is measured instead.
    """
    modes = ["raise_signal", "replica"]
    if sys.platform != "win32":
        modes.append("process_kill")
    return tuple(modes)


def main() -> None:
    print(f"platform={sys.platform} python={sys.version.split()[0]}")
    print(f"llm_response_seconds={LLM_RESPONSE_SECONDS}")
    for mode in _modes():
        _run(mode)


if __name__ == "__main__":
    main()