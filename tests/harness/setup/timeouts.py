"""Shared per-test timeout policy for the test suite.

The Windows CI leg intermittently loses an xdist worker when a transient runner
stall pushes one test past the per-test budget, because the pytest-timeout
thread method terminates the worker process with ``os._exit``. One shared
budget keeps that amplifier far above any observed stall, and the CI test job
carries a wall-clock cap so a genuine hang still terminates the job.
"""

from __future__ import annotations

import os

CI_PER_TEST_TIMEOUT_SECONDS = 60


def ci_per_test_timeout() -> int | None:
    """Return the CI per-test budget in seconds, or None outside CI."""
    if os.getenv("CI") == "true":
        return CI_PER_TEST_TIMEOUT_SECONDS
    return None
