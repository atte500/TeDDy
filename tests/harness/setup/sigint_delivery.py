"""Shared test seam for observing SIGINT delivery.

``raise_interrupt`` delivers SIGINT through ``signal.raise_signal`` today and
targets the main thread through ``signal.pthread_kill`` on POSIX after the
interrupt-latency fix. Tests must observe delivery without raising
KeyboardInterrupt in the test process, and they must keep observing it when the
production primitive changes. ``stub_sigint_delivery`` patches whichever
primitive the running platform exposes and records every delivered signal in one
shared list.

Recording alone leaves the installed handler unrun, so an in-process test can
never reach the real guard. ``SigintDeliveryMode.ROUTE_TO_HANDLER`` additionally
invokes the disposition installed at press time, which is how an acceptance run
drives the production interrupt lifecycle instead of a stand-in.
"""

from __future__ import annotations

import signal
from enum import Enum
from typing import Any

DeliveredSignals = list[int]


class SigintDeliveryMode(Enum):
    """How a stubbed SIGINT press is delivered inside the test process.

    ``RECORD`` records the delivered signal and stops there, so the suite never
    runs a handler. ``ROUTE_TO_HANDLER`` also invokes whichever SIGINT handler
    is installed at press time, so an in-process test drives the real
    ``InterruptGuard`` (including its WAITING/EXECUTING branch) instead of a
    stand-in.
    """

    RECORD = "record"
    ROUTE_TO_HANDLER = "route_to_handler"


def stub_sigint_delivery(
    monkeypatch: Any, mode: SigintDeliveryMode = SigintDeliveryMode.RECORD
) -> DeliveredSignals:
    """Patch the platform SIGINT primitives and return the delivery recorder.

    The recorder collects each delivered signal number so a test can assert that
    delivery happened regardless of which primitive the production code uses.
    ``signal.pthread_kill`` is patched only where the platform exposes it,
    because Windows lacks the attribute and the test process must never receive a
    real signal.

    In ``ROUTE_TO_HANDLER`` mode the patched primitive also invokes the SIGINT
    handler installed at press time. The disposition is resolved then, not at
    stub time, because the run installs its handler after this stub is applied.
    A non-callable disposition such as ``SIG_IGN`` is skipped, and the signal is
    recorded before routing so a handler that raises still leaves evidence of
    the press.
    """
    delivered: DeliveredSignals = []

    def _deliver(sig: int) -> None:
        delivered.append(sig)
        if mode is not SigintDeliveryMode.ROUTE_TO_HANDLER:
            return
        installed = signal.getsignal(signal.SIGINT)
        if callable(installed):
            installed(sig, None)

    monkeypatch.setattr(signal, "raise_signal", _deliver)
    if hasattr(signal, "pthread_kill"):
        monkeypatch.setattr(
            signal,
            "pthread_kill",
            lambda thread_id, sig: _deliver(sig),
            raising=False,
        )
    return delivered
