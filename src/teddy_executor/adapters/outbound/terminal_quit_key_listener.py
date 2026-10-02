"""Concrete terminal single-key quit listener (Bug 56 bare-`q`).

An environment-agnostic ``IQuitKeyListener`` for terminals that never deliver
a Ctrl+C byte: when the quit key is pressed the listener invokes its
Constructor-Injected ``on_quit`` callback, which self-delivers SIGINT so the
shared ``InterruptGuard`` runs its already-tested WAITING/EXECUTING branch
unchanged.

The listener is a no-op when stdin is not a TTY, backs off while another reader
owns stdin (``core.utils.stdin_ownership``), and uses ``msvcrt.kbhit()`` on
Windows (no terminal-mode change).
"""

from __future__ import annotations

import importlib
import os
import select
import signal
import sys
import threading
from typing import Any, Optional, cast

from teddy_executor.core.ports.outbound.quit_key_listener import QuitCallback
from teddy_executor.core.utils.stdin_ownership import is_stdin_owned

# The ASCII code of the bare quit key (`q`).
QUIT_KEY = 0x71

# Seconds the reader sleeps between polls when no byte is ready.
_POLL_INTERVAL = 0.05


class TerminalQuitKeyListener:
    """Concrete IQuitKeyListener supplied as a process-global singleton.

    Constructor-Injected ``on_quit`` is the trigger hook invoked when the quit
    key is pressed; when omitted, a quit self-delivers SIGINT to the process so
    the shared ``InterruptGuard`` handles it unchanged.
    """

    def __init__(self, on_quit: Optional[QuitCallback] = None) -> None:
        self._on_quit = on_quit
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._saved_attrs: Optional[list[Any]] = None

    # --- lifecycle ---

    def start(self) -> None:
        """Begin listening for the quit key (no-op when stdin is not a TTY)."""
        if not sys.stdin.isatty():
            return
        self._stop_event.clear()
        self._enter_noncanonical_mode()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop listening and restore the terminal's saved cooked mode."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            thread.join()
            self._thread = None
        self._restore_mode()

    # --- terminal mode (POSIX) ---

    def _enter_noncanonical_mode(self) -> None:
        """Switch the controlling TTY to non-canonical mode, keeping ISIG SET."""
        if sys.platform == "win32":
            return
        termios = cast(Any, importlib.import_module("termios"))
        fd = sys.stdin.fileno()
        attrs = termios.tcgetattr(fd)
        self._saved_attrs = list(attrs)
        # Disable canonical line editing and echo, but KEEP ISIG so a real
        # Ctrl+C still generates SIGINT alongside the bare-`q` trigger.
        attrs[3] &= ~(termios.ICANON | termios.ECHO)
        attrs[6][termios.VMIN] = 1
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSAFLUSH, attrs)

    def _restore_mode(self) -> None:
        """Reinstate the terminal mode saved by ``_enter_noncanonical_mode``."""
        if sys.platform == "win32" or self._saved_attrs is None:
            return
        termios = cast(Any, importlib.import_module("termios"))
        fd = sys.stdin.fileno()
        termios.tcsetattr(fd, termios.TCSAFLUSH, self._saved_attrs)
        self._saved_attrs = None

    # --- reader ---

    def _read_loop(self) -> None:
        """Poll for the quit key, backing off while another reader owns stdin."""
        while not self._stop_event.is_set():
            if is_stdin_owned():
                self._stop_event.wait(_POLL_INTERVAL)
                continue
            byte = self._read_one_byte()
            if byte is None:
                self._stop_event.wait(_POLL_INTERVAL)
                continue
            if self._process_byte(byte):
                break

    def _read_one_byte(self) -> Optional[int]:
        """Read one byte from stdin, or None when none is available."""
        if sys.platform == "win32":
            return self._read_one_byte_windows()
        return self._read_one_byte_posix()

    def _read_one_byte_posix(self) -> Optional[int]:
        """Read one byte from the controlling TTY (POSIX)."""
        try:
            fd = sys.stdin.fileno()
        except (ValueError, OSError):
            return None
        ready, _, _ = select.select([fd], [], [], _POLL_INTERVAL)
        if not ready:
            return None
        try:
            data = os.read(fd, 1)
        except OSError:
            return None
        if not data:
            return None
        return data[0]

    def _read_one_byte_windows(self) -> Optional[int]:
        """Read one byte via msvcrt (Windows); no terminal-mode change."""
        msvcrt = cast(Any, importlib.import_module("msvcrt"))
        if not msvcrt.kbhit():
            return None
        return ord(msvcrt.getwch())

    def _process_byte(self, byte: int) -> bool:
        """Trigger the quit on the quit key; return whether the reader is done."""
        if byte == QUIT_KEY:
            self._trigger()
            return True
        return False

    def _trigger(self) -> None:
        """Invoke the injected hook, or self-deliver SIGINT by default."""
        if self._on_quit is not None:
            self._on_quit()
            return
        os.kill(os.getpid(), signal.SIGINT)
