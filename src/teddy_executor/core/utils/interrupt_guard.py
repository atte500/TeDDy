"""Two-phase Ctrl+C interrupt guard.

The guard installs the process SIGINT handler and exposes the EXECUTING
phase context manager plus an `interrupted` threading.Event that the
execution loop consults after each action to skip the remaining work
gracefully (the report is still generated so the audit trail is preserved).
Phase semantics: in the default WAITING phase (prompts, planning LLM call) a
signal raises KeyboardInterrupt immediately — nothing is in flight. In
EXECUTING the first signal sets the flag so the in-flight
action can drain gracefully; a second signal within the grace window
escalates to immediate termination; after the window the signal is
treated as a new first signal (the window restarts).

The grace window is a module constant and the monotonic clock is
Constructor-Injected
so tests advance time deterministically (no sleeps). The module stays
import-free of DI frameworks (hexagonal core boundary).
"""

import signal
import sys
import threading
from collections.abc import Callable
from contextlib import contextmanager
from types import FrameType
from typing import Any, Iterator, Optional

# Grace-window duration (seconds): how long a second Ctrl+C during action
# execution is treated as an escalation (immediate force-kill) instead of a
# new graceful-drain request. A code constant per explicit product decision
# (no longer tunable from the configuration layer).
GRACE_WINDOW_SECONDS = 2.0

# The single shared session-interrupt notice (Bug 56): the now-inaccurate
# "(Ctrl+C)" fragment was dropped so the user-visible boundary notice and the
# audit-trail drain reason render identically from one source of truth.
INTERRUPT_REASON = "Interrupted by user."


# Marks that the guard owns no SIGINT disposition. A dedicated sentinel
# (not None) keeps the claim explicit, because signal.getsignal() may
# legitimately return None for a handler not set from Python.
_UNCLAIMED_DISPOSITION = object()


class InterruptGuard:
    """Installs the SIGINT handler, owns the disposition, and tracks the
    WAITING/EXECUTING phase.

    Constructor-Injected dependency:
    - monotonic: the time source for grace-window bookkeeping (e.g.,
      time.monotonic in production; a controllable fake in tests).
    """

    def __init__(
        self,
        monotonic: Callable[[], float],
    ) -> None:
        self._grace_window = GRACE_WINDOW_SECONDS
        self._monotonic = monotonic
        self.interrupted = threading.Event()
        # The key that triggered the interrupt (e.g. "q"), recorded by the
        # quit-key listener before it self-delivers SIGINT. None means a
        # genuine Ctrl+C (or a direct interrupted.set() in tests).
        self.source: Optional[str] = None
        self._executing = False
        self._first_signal_at: Optional[float] = None
        # The disposition restore() reinstates, or the sentinel while the
        # guard owns nothing. One guard holds at most one claim: two owners
        # each taking their own snapshot would restore each other's handler.
        self._previous_handler: Any = _UNCLAIMED_DISPOSITION

    def install(self) -> object:
        """Takes ownership of the SIGINT disposition and installs the handler.

        Returns the previous disposition for callers that only inspect it;
        the guard itself owns restoration through restore(). A second install
        without an intervening restore is a programming defect, so the
        contract fails fast instead of taking a second snapshot.
        """
        assert self._previous_handler is _UNCLAIMED_DISPOSITION, (
            "InterruptGuard already owns the process SIGINT disposition "
            f"({signal.getsignal(signal.SIGINT)!r}); call restore() before "
            "installing again."
        )
        self._previous_handler = signal.signal(signal.SIGINT, self._handle_signal)
        return self._previous_handler

    def restore(self) -> None:
        """Reinstates the captured disposition and releases the claim.

        Releasing (rather than latching) ownership lets one memoized-container
        guard bracket a later command, while a genuine nested install still
        fails its contract.
        """
        assert self._previous_handler is not _UNCLAIMED_DISPOSITION, (
            "InterruptGuard.restore() requires a matching install(); "
            "no SIGINT disposition is owned."
        )
        signal.signal(signal.SIGINT, self._previous_handler)
        self._previous_handler = _UNCLAIMED_DISPOSITION

    def clear_source(self) -> None:
        """Forget which key triggered a previous run's interrupt.

        Called at bracket entry: one memoized container keeps a single guard
        alive across in-process commands, so a leftover source would name the
        previous run's key in this run's notice.
        """
        self.source = None

    def record_source(self, source: str) -> None:
        """Record which key triggered the interrupt (e.g. ``"q"``).

        The quit-key listener's ``on_quit`` callback calls this BEFORE
        self-delivering SIGINT so the boundary notice can name the key the
        user actually pressed instead of defaulting to ``Ctrl+C``.
        """
        self.source = source

    def _handle_signal(self, signum: int, frame: Optional[FrameType]) -> None:
        """The installed SIGINT handler; branches on the current phase."""
        if not self._executing:
            # WAITING (or the default phase before any context manager):
            # nothing is in flight — exit immediately.
            raise KeyboardInterrupt
        now = self._monotonic()
        if self._first_signal_at is None:
            # First signal during EXECUTING: begin the graceful drain.
            self._first_signal_at = now
            self.interrupted.set()
            return
        if now - self._first_signal_at <= self._grace_window:
            # Second signal within the grace window: force-kill escape hatch.
            raise KeyboardInterrupt
        # Grace expired: a late second signal is a NEW first signal —
        # the window restarts (the drain flag stays set).
        self._first_signal_at = now
        self.interrupted.set()

    @contextmanager
    def enter_executing(self) -> Iterator["InterruptGuard"]:
        """Marks the EXECUTING phase: signals drain, then escalate.

        A stale interrupted flag is cleared at entry so an interrupt from a
        previous action cannot skip the next one; exiting restores the
        WAITING (raising) phase.
        """
        self.interrupted.clear()
        self._first_signal_at = None
        self._executing = True
        try:
            yield self
        finally:
            self._executing = False
            self._first_signal_at = None


def raise_interrupt() -> None:
    """Deliver SIGINT in-process so the installed handler runs on every platform.

    ``os.kill(os.getpid(), signal.SIGINT)`` terminates the process on Windows
    through ``TerminateProcess`` instead of invoking the Python SIGINT handler,
    which suppresses the interrupt notice. On POSIX the signal targets the main
    thread through ``signal.pthread_kill``, so delivery wakes a blocked main
    thread at its next checkpoint instead of waiting for the calling thread to
    return. Windows and any platform without ``pthread_kill`` use
    ``signal.raise_signal``, which keeps the CRT raise path so the installed
    handler still runs there.
    """
    if sys.platform != "win32" and hasattr(signal, "pthread_kill"):
        main_ident = threading.main_thread().ident
        if main_ident is not None:
            signal.pthread_kill(main_ident, signal.SIGINT)
            return
    signal.raise_signal(signal.SIGINT)
