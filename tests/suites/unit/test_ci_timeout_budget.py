"""Regression coverage for the shared CI per-test timeout budget.

A transient runner stall pushed one test past the old 15 second budget, and the
pytest-timeout thread method then terminated the xdist worker, so the whole
suite failed on whichever test was running. The budget must stay far above an
observed stall and must never leak into local runs.
"""

from __future__ import annotations

import pytest

from tests.harness.setup.timeouts import (
    CI_PER_TEST_TIMEOUT_SECONDS,
    ci_per_test_timeout,
)

_OBSERVED_RUNNER_STALL_SECONDS = 20


def test_budget_applies_only_inside_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI", "true")

    assert ci_per_test_timeout() == CI_PER_TEST_TIMEOUT_SECONDS


def test_budget_is_absent_outside_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI", raising=False)

    assert ci_per_test_timeout() is None


def test_budget_leaves_ample_headroom_over_an_observed_stall() -> None:
    assert CI_PER_TEST_TIMEOUT_SECONDS >= 3 * _OBSERVED_RUNNER_STALL_SECONDS
