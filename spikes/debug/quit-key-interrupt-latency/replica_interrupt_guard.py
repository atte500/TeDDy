"""Sandbox replica of the shared SIGINT delivery helper.

The production helper calls ``signal.raise_signal`` unconditionally. On POSIX
that call targets the *calling* thread, so a raise from the quit-key reader
thread leaves the main thread blocked until its current call returns. The
proposed fix targets the main thread on POSIX. Windows keeps the CRT raise
path, which the cross-platform fix requires.
"""

import signal
import sys
import threading


def raise_interrupt() -> None:
    """Deliver SIGINT to the main thread on POSIX, or via the CRT on Windows."""
    if sys.platform != "win32" and hasattr(signal, "pthread_kill"):
        main_ident = threading.main_thread().ident
        if main_ident is not None:
            signal.pthread_kill(main_ident, signal.SIGINT)
            return
    signal.raise_signal(signal.SIGINT)