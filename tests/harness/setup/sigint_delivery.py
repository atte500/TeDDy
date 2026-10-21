"""Shared test seam for observing SIGINT delivery.

``raise_interrupt`` delivers SIGINT through ``signal.raise_signal`` today and
targets the main thread through ``signal.pthread_kill`` on POSIX after the
interrupt-latency fix. Tests must observe delivery without raising
KeyboardInterrupt in the test process, and they must keep observing it when the
production primitive changes. ``stub_sigint_delivery`` patches whichever
primitive the running platform exposes and records every delivered signal in one
shared list.
"""

from __future__ import annotations

import signal
from typing import Any

DeliveredSignals = list[int]


def stub_sigint_delivery(monkeypatch: Any) -> DeliveredSignals:
    """Patch the platform SIGINT primitives and return the delivery recorder.

    The recorder collects each delivered signal number so a test can assert that
    delivery happened regardless of which primitive the production code uses.
    ``signal.pthread_kill`` is patched only where the platform exposes it,
    because Windows lacks the attribute and the test process must never receive a
    real signal.
    """
    delivered: DeliveredSignals = []

    def _record(sig: int) -> None:
        delivered.append(sig)

    monkeypatch.setattr(signal, "raise_signal", _record)
    if hasattr(signal, "pthread_kill"):
        monkeypatch.setattr(
            signal,
            "pthread_kill",
            lambda thread_id, sig: _record(sig),
            raising=False,
        )
    return delivered
