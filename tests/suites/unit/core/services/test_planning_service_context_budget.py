"""Unit tests for the over-budget context guardrail (case file 07 Measure 2).

The guardrail turns an oversized request into a loud, user-visible failure
instead of a silent stall. These tests pin the three edge cases and the error
message at the extracted `PlanningService._check_context_budget` seam, mirroring
the direct-helper style already used by `test_run_preflight_check_raises_on_error`.
"""

import pytest

from teddy_executor.core.domain.models.exceptions import ConfigurationError
from teddy_executor.core.ports.outbound import ILlmClient
from teddy_executor.core.services.planning_service import PlanningService

_MODEL = "test-model"
_WINDOW = 128_000


def _service_with_llm(env):
    """Resolve a PlanningService and its Constructor-Injected ILlmClient double."""
    mock_llm = env.mock_port(ILlmClient)
    service = env.get_service(PlanningService)
    return service, mock_llm


def test_over_budget_request_raises_configuration_error(env):
    """Edge case: a strict excess raises a clear, user-visible error."""
    service, mock_llm = _service_with_llm(env)
    mock_llm.get_context_window.return_value = _WINDOW

    with pytest.raises(ConfigurationError) as exc_info:
        service._check_context_budget(_WINDOW + 1, _MODEL)

    message = str(exc_info.value)
    assert "Context Window Exceeded" in message
    assert str(_WINDOW + 1) in message
    assert str(_WINDOW) in message
    assert _MODEL in message


def test_exact_boundary_does_not_raise(env):
    """Edge case: a request that exactly fills the window is allowed."""
    service, mock_llm = _service_with_llm(env)
    mock_llm.get_context_window.return_value = _WINDOW

    service._check_context_budget(_WINDOW, _MODEL)  # must not raise


def test_unknown_zero_window_does_not_raise(env):
    """Edge case: a zero window is unknown, so the guardrail is disabled."""
    service, mock_llm = _service_with_llm(env)
    mock_llm.get_context_window.return_value = 0

    service._check_context_budget(_WINDOW * 10, _MODEL)  # must not raise


def test_unknown_negative_window_does_not_raise(env):
    """Edge case: a negative window is unknown, so the guardrail is disabled."""
    service, mock_llm = _service_with_llm(env)
    mock_llm.get_context_window.return_value = -1

    service._check_context_budget(_WINDOW * 10, _MODEL)  # must not raise
