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

import pytest

from tests.harness.setup.sigint_delivery import stub_sigint_delivery


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
