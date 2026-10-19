"""Sandbox replica: the proposed cross-platform SIGINT self-delivery.

Replaces the production ``os.kill(os.getpid(), signal.SIGINT)`` call, which on
Windows terminates the process through ``TerminateProcess`` instead of invoking
the registered Python SIGINT handler.
"""

import signal


def raise_interrupt() -> None:
    """Deliver SIGINT in-process through the Python-level handler."""
    signal.raise_signal(signal.SIGINT)