"""Two-phase Ctrl+C interrupt guard.

The guard installs the process SIGINT handler and exposes WAITING /
EXECUTING phase context managers plus an `interrupted` threading.Event
that the execution loop consults after each action to skip the remaining
work gracefully (the report is still generated so the audit trail is
preserved). Phase semantics (Task-Brief-approved): in WAITING (prompts,
planning LLM call) a signal raises KeyboardInterrupt immediately — nothing
is in flight. In EXECUTING the first signal sets the flag so the in-flight
action can drain gracefully; a second signal within the grace window
escalates to immediate termination; after the window the signal is
treated as a new first signal (the window restarts).

The grace window is a module constant and the monotonic clock is
Constructor-Injected
so tests advance time deterministically (no sleeps). The module stays
import-free of DI frameworks (hexagonal core boundary).
"""

import signal
import threading
from collections.abc import Callable
from contextlib import contextmanager
from types import FrameType
from typing import Iterator, Optional

# Grace-window duration (seconds): how long a second Ctrl+C during action
# execution is treated as an escalation (immediate force-kill) instead of a
# new graceful-drain request. A code constant per explicit product decision
# (no longer tunable from the configuration layer).
GRACE_WINDOW_SECONDS = 2.0

# The single shared session-interrupt notice (Bug 56): the now-inaccurate
# "(Ctrl+C)" fragment was dropped so the user-visible boundary notice and the
# audit-trail drain reason render identically from one source of truth.
INTERRUPT_REASON = "Interrupted by user."


class InterruptGuard:
    """Installs the SIGINT handler and tracks the WAITING/EXECUTING phase.

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
        self._executing = False
        self._first_signal_at: Optional[float] = None

    def install(self) -> object:
        """Registers the SIGINT handler and returns the previous disposition.

        The caller owns restoration: keep the returned value and pass it to
        signal.signal(SIGINT, ...) when the guard's lifetime ends.
        """
        return signal.signal(signal.SIGINT, self._handle_signal)

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
    def enter_waiting(self) -> Iterator["InterruptGuard"]:
        """Marks the WAITING phase: signals raise KeyboardInterrupt."""
        self._executing = False
        self._first_signal_at = None
        try:
            yield self
        finally:
            self._first_signal_at = None

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
