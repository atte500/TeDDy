"""Unit tests: InterruptGuard contract (two-phase Ctrl+C interrupt).

The guard installs the process SIGINT handler and exposes WAITING /
EXECUTING phase context managers plus an `interrupted` threading.Event.
Phase semantics (Task-Brief-approved): in WAITING (prompts, planning
LLM call) a signal raises KeyboardInterrupt immediately — nothing is in
flight. In EXECUTING the first signal sets the flag so the in-flight
action can drain gracefully; a second signal within the grace window
escalates to immediate termination. The grace window is a module
constant and the monotonic clock is Constructor-Injected for
deterministic escalation tests (no sleeps).
"""

import signal
import sys
import threading

import pytest

from teddy_executor.core.utils.interrupt_guard import InterruptGuard, raise_interrupt


class _FakeClock:
    """Controllable monotonic clock double (Constructor-Injected)."""

    def __init__(self) -> None:
        self._now = 0.0

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


@pytest.fixture
def clock():
    return _FakeClock()


@pytest.fixture
def guard(clock):
    return InterruptGuard(monotonic=clock)


class TestInterruptGuardContract:
    """Construction contract."""

    def test_interrupted_event_initially_unset(self, guard) -> None:
        # Assert: the guard exposes a threading.Event, unset before any signal.
        assert isinstance(guard.interrupted, threading.Event)
        assert not guard.interrupted.is_set()

    def test_install_returns_previous_handler(self, guard) -> None:
        # Arrange
        previous = signal.getsignal(signal.SIGINT)

        # Act / Assert: install() returns the previous handler so callers
        # can restore the original disposition.
        try:
            assert guard.install() is previous
        finally:
            signal.signal(signal.SIGINT, previous)


class TestPhaseSignalHandling:
    """WAITING raises immediately; EXECUTING drains, then escalates."""

    def _installed_handler(self, guard):
        """Installs the guard's handler and returns (handler, previous)."""
        previous = signal.getsignal(signal.SIGINT)
        guard.install()
        handler = signal.getsignal(signal.SIGINT)
        assert callable(handler), "install() must register a SIGINT handler"
        return handler, previous

    def test_default_phase_signal_raises_keyboard_interrupt(self, guard) -> None:
        # Before any phase is entered, the guard is effectively WAITING:
        # nothing is in flight, so a signal must raise immediately.
        handler, previous = self._installed_handler(guard)
        try:
            with pytest.raises(KeyboardInterrupt):
                handler(signal.SIGINT, None)
        finally:
            signal.signal(signal.SIGINT, previous)

    def test_waiting_phase_signal_raises_keyboard_interrupt(self, guard) -> None:
        handler, previous = self._installed_handler(guard)
        try:
            with guard.enter_waiting():
                with pytest.raises(KeyboardInterrupt):
                    handler(signal.SIGINT, None)
        finally:
            signal.signal(signal.SIGINT, previous)

    def test_executing_first_signal_sets_flag_without_raising(self, guard) -> None:
        handler, previous = self._installed_handler(guard)
        try:
            with guard.enter_executing():
                # Act: the first signal during EXECUTING must NOT raise —
                # the in-flight action is allowed to finish gracefully.
                handler(signal.SIGINT, None)

                # Assert
                assert guard.interrupted.is_set()
        finally:
            signal.signal(signal.SIGINT, previous)

    def test_executing_second_signal_within_grace_window_escalates(
        self, guard, clock
    ) -> None:
        handler, previous = self._installed_handler(guard)
        try:
            with guard.enter_executing():
                handler(signal.SIGINT, None)  # t=0: graceful drain begins
                clock.advance(1.0)  # t=1 < 2.0s grace window
                with pytest.raises(KeyboardInterrupt):
                    handler(signal.SIGINT, None)  # second signal: force-kill
        finally:
            signal.signal(signal.SIGINT, previous)

    def test_second_signal_after_grace_window_restarts_window(
        self, guard, clock
    ) -> None:
        handler, previous = self._installed_handler(guard)
        try:
            with guard.enter_executing():
                handler(signal.SIGINT, None)  # t=0
                clock.advance(3.0)  # t=3 > 2.0s window: grace expired
                # A late second signal is treated as a NEW first signal.
                handler(signal.SIGINT, None)
                clock.advance(1.0)  # t=4 < 2.0s since the new first signal
                with pytest.raises(KeyboardInterrupt):
                    handler(signal.SIGINT, None)
        finally:
            signal.signal(signal.SIGINT, previous)

    def test_enter_executing_clears_stale_interrupted_flag(self, guard) -> None:
        # A stale flag must not skip the next turn's actions: a fresh
        # executing window starts clean.
        with guard.enter_executing():
            guard.interrupted.set()

        # Act / Assert
        with guard.enter_executing():
            assert not guard.interrupted.is_set()

    def test_exiting_executing_restores_waiting_phase(self, guard) -> None:
        handler, previous = self._installed_handler(guard)
        try:
            with guard.enter_executing():
                pass
            # After the executing window exits, a signal raises again.
            with pytest.raises(KeyboardInterrupt):
                handler(signal.SIGINT, None)
        finally:
            signal.signal(signal.SIGINT, previous)


@pytest.mark.skipif(
    not hasattr(signal, "SIGINT"),
    reason="SIGINT delivery is unavailable on this platform",
)
class TestRealSignalDelivery:
    """End-to-end handler delivery via the shared raise_interrupt helper."""

    def test_real_sigint_sets_interrupted_flag_during_executing(self, guard) -> None:
        # Arrange
        previous = signal.getsignal(signal.SIGINT)
        try:
            guard.install()
            with guard.enter_executing():
                # Act: deliver a real SIGINT through the same shared helper the
                # production quit paths use.
                raise_interrupt()

                # Assert: the installed handler set the drain flag.
                assert guard.interrupted.is_set()
        finally:
            signal.signal(signal.SIGINT, previous)


class TestMainThreadDeliveryPrimitive:
    """POSIX delivery targets the main thread; Windows keeps the CRT raise.

    On POSIX ``signal.raise_signal`` delivers to the calling thread, so a raise
    from the quit-key reader leaves a blocked main thread waiting for its
    current call to return. Delivery must target the main thread instead. On
    Windows, where ``signal.pthread_kill`` does not exist, the CRT raise path
    must stay intact so the installed handler still runs.
    """

    @pytest.mark.skipif(
        sys.platform == "win32" or not hasattr(signal, "pthread_kill"),
        reason="pthread_kill is unavailable on this platform",
    )
    def test_posix_delivery_targets_the_main_thread(self, monkeypatch) -> None:
        # Arrange: record both primitives instead of delivering a real signal.
        killed: list[tuple[int, int]] = []
        raised: list[int] = []
        monkeypatch.setattr(signal, "raise_signal", lambda sig: raised.append(sig))
        monkeypatch.setattr(
            signal,
            "pthread_kill",
            lambda thread_id, sig: killed.append((thread_id, sig)),
            raising=False,
        )

        # Act
        raise_interrupt()

        # Assert: the main thread is the delivery target and the CRT raise is
        # not used on POSIX.
        main_ident = threading.main_thread().ident
        assert main_ident is not None, "the main thread must carry an identifier"
        assert killed == [(main_ident, signal.SIGINT)]
        assert raised == []

    @pytest.mark.skipif(
        sys.platform == "win32" or not hasattr(signal, "pthread_kill"),
        reason="pthread_kill is unavailable on this platform",
    )
    def test_posix_delivery_from_a_worker_targets_the_main_thread(
        self, monkeypatch
    ) -> None:
        # Arrange: a worker delivers, exactly as the quit-key reader does.
        killed: list[tuple[int, int]] = []
        monkeypatch.setattr(signal, "raise_signal", lambda sig: None)
        monkeypatch.setattr(
            signal,
            "pthread_kill",
            lambda thread_id, sig: killed.append((thread_id, sig)),
            raising=False,
        )

        # Act
        worker = threading.Thread(target=raise_interrupt)
        worker.start()
        worker.join()

        # Assert: delivery names the main thread, not the calling worker.
        main_ident = threading.main_thread().ident
        assert main_ident is not None, "the main thread must carry an identifier"
        assert killed == [(main_ident, signal.SIGINT)]

    def test_windows_delivery_uses_raise_signal(self, monkeypatch) -> None:
        # Arrange: simulate the Windows leg, where pthread_kill is unavailable.
        monkeypatch.setattr(sys, "platform", "win32")
        raised: list[int] = []
        killed: list[tuple[int, int]] = []
        monkeypatch.setattr(signal, "raise_signal", lambda sig: raised.append(sig))
        if hasattr(signal, "pthread_kill"):
            monkeypatch.setattr(
                signal,
                "pthread_kill",
                lambda thread_id, sig: killed.append((thread_id, sig)),
                raising=False,
            )

        # Act
        raise_interrupt()

        # Assert: the CRT raise path is kept and no POSIX target is used.
        assert raised == [signal.SIGINT]
        assert killed == []
