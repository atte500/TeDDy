"""Unit tests for the shared SIGINT delivery seam.

``raise_interrupt`` delivers SIGINT through ``signal.raise_signal`` today and
will target the main thread through ``signal.pthread_kill`` on POSIX after the
interrupt-latency fix. ``stub_sigint_delivery`` patches whichever primitive the
running platform exposes so a test can observe delivery without raising
KeyboardInterrupt in the test process. These tests pin that the seam records
delivery from both primitives into one shared list.
"""

import signal
import threading
import time
from collections.abc import Iterator

import pytest

from teddy_executor.core.utils.interrupt_guard import InterruptGuard, raise_interrupt
from tests.harness.setup.sigint_delivery import (
    SigintDeliveryMode,
    stub_sigint_delivery,
)


class TestStubSigintDelivery:
    def test_records_raise_signal_delivery(self, monkeypatch):
        delivered = stub_sigint_delivery(monkeypatch)

        signal.raise_signal(signal.SIGINT)

        assert delivered == [signal.SIGINT]

    @pytest.mark.skipif(
        not hasattr(signal, "pthread_kill"),
        reason="pthread_kill is unavailable on this platform",
    )
    def test_records_pthread_kill_delivery(self, monkeypatch):
        delivered = stub_sigint_delivery(monkeypatch)

        signal.pthread_kill(threading.main_thread().ident, signal.SIGINT)

        assert delivered == [signal.SIGINT]

    @pytest.mark.skipif(
        not hasattr(signal, "pthread_kill"),
        reason="pthread_kill is unavailable on this platform",
    )
    def test_both_primitives_share_one_recorder_list(self, monkeypatch):
        delivered = stub_sigint_delivery(monkeypatch)

        signal.raise_signal(signal.SIGINT)
        signal.pthread_kill(threading.main_thread().ident, signal.SIGINT)

        assert delivered == [signal.SIGINT, signal.SIGINT]


class _RecordingHandler:
    """Callable SIGINT handler double recording each ``(signum, frame)`` call."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, object]] = []

    def __call__(self, signum: int, frame: object) -> None:
        self.calls.append((signum, frame))


@pytest.fixture
def installed_handler() -> Iterator[_RecordingHandler]:
    """Installs a recording SIGINT handler and restores the prior disposition."""
    handler = _RecordingHandler()
    previous = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, handler)
    try:
        yield handler
    finally:
        signal.signal(signal.SIGINT, previous)


class TestRoutedSigintDelivery:
    """ROUTE_TO_HANDLER drives whichever handler the process has installed.

    An in-process acceptance run needs the real interrupt guard to observe a
    simulated press, so this mode invokes the installed handler synchronously
    instead of stopping at the recorder. RECORD stays the default so the
    existing recorder-only callers keep observing delivery with no handler.
    """

    def test_routed_raise_signal_invokes_the_installed_handler(
        self, monkeypatch, installed_handler
    ) -> None:
        delivered = stub_sigint_delivery(
            monkeypatch, mode=SigintDeliveryMode.ROUTE_TO_HANDLER
        )

        signal.raise_signal(signal.SIGINT)

        assert installed_handler.calls == [(signal.SIGINT, None)]
        assert delivered == [signal.SIGINT]

    @pytest.mark.skipif(
        not hasattr(signal, "pthread_kill"),
        reason="pthread_kill is unavailable on this platform",
    )
    def test_routed_pthread_kill_invokes_the_installed_handler(
        self, monkeypatch, installed_handler
    ) -> None:
        delivered = stub_sigint_delivery(
            monkeypatch, mode=SigintDeliveryMode.ROUTE_TO_HANDLER
        )

        signal.pthread_kill(threading.main_thread().ident, signal.SIGINT)

        assert installed_handler.calls == [(signal.SIGINT, None)]
        assert delivered == [signal.SIGINT]

    def test_record_mode_never_invokes_the_installed_handler(
        self, monkeypatch, installed_handler
    ) -> None:
        delivered = stub_sigint_delivery(monkeypatch)

        signal.raise_signal(signal.SIGINT)

        assert installed_handler.calls == []
        assert delivered == [signal.SIGINT]

    def test_routed_mode_skips_a_non_callable_disposition(self, monkeypatch) -> None:
        previous = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            delivered = stub_sigint_delivery(
                monkeypatch, mode=SigintDeliveryMode.ROUTE_TO_HANDLER
            )

            signal.raise_signal(signal.SIGINT)

            assert delivered == [signal.SIGINT]
        finally:
            signal.signal(signal.SIGINT, previous)

    def test_routed_mode_drives_the_real_interrupt_guard(self, monkeypatch) -> None:
        """The mode's purpose: a simulated press reaches the real guard.

        The guard's EXECUTING branch only sets its drain flag, so nothing is
        raised in the test process and no real signal is delivered.
        """
        guard = InterruptGuard(monotonic=time.monotonic)
        guard.install()
        try:
            stub_sigint_delivery(monkeypatch, mode=SigintDeliveryMode.ROUTE_TO_HANDLER)

            with guard.enter_executing():
                raise_interrupt()

            assert guard.interrupted.is_set()
        finally:
            guard.restore()
