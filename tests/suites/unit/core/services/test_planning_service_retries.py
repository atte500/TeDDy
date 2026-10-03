from typing import Any

import pytest

from teddy_executor.core.services.planning_service import PlanningService
from teddy_executor.core.domain.models.planning_ports import PlanningPorts
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from tests.harness.setup.mocking import POSIXPathMock, register_mock


def test_planning_service_uses_configured_retries(container: Any) -> None:
    # Arrange
    mock_config = register_mock(container, IConfigService)
    mock_llm = register_mock(container, ILlmClient)

    ports = container.resolve(PlanningPorts)

    # Configure 5 retries.
    def mock_get_setting(key: str, default: Any = None) -> Any:
        if key == "llm.max_retries":
            return 5
        return default

    mock_config.get_setting.side_effect = mock_get_setting

    # Mock LLM to return empty responses
    # Use POSIXPathMock directly for non-port objects to allow arbitrary attributes
    mock_response = POSIXPathMock()
    mock_response.choices = []
    mock_llm.get_completion.return_value = mock_response

    service = PlanningService(ports)

    # Act
    service._perform_generation_with_retry(messages=[], model="test-model")

    # Assert
    # 5 attempts expected if PlanningService is updated to use the config
    assert mock_llm.get_completion.call_count == 5


def test_retry_loop_accumulates_cost_across_billed_attempts(container: Any) -> None:
    """A billed empty attempt that triggers a retry stays in the turn total."""
    # Arrange
    mock_config = register_mock(container, IConfigService)
    mock_llm = register_mock(container, ILlmClient)

    ports = container.resolve(PlanningPorts)

    mock_config.get_setting.side_effect = lambda key, default=None: (
        3 if key == "llm.max_retries" else default
    )

    empty_response = POSIXPathMock()
    empty_response.choices = []

    success_choice = POSIXPathMock()
    success_choice.message.content = "# Plan\nContent"
    success_response = POSIXPathMock()
    success_response.choices = [success_choice]

    mock_llm.get_completion.side_effect = [empty_response, success_response]
    mock_llm.get_completion_cost.side_effect = [0.1, 0.2]

    service = PlanningService(ports)

    # Act
    _, plan_content, turn_cost = service._perform_generation_with_retry(
        messages=[], model="test-model"
    )

    # Assert: both billed attempts contribute; the retry does not discard the first
    assert mock_llm.get_completion.call_count == 2
    assert plan_content == "# Plan\nContent"
    assert turn_cost == pytest.approx(0.3)


def test_single_successful_attempt_is_billed_exactly_once(container: Any) -> None:
    """A successful first attempt is counted exactly once (no double-counting)."""
    # Arrange
    mock_config = register_mock(container, IConfigService)
    mock_llm = register_mock(container, ILlmClient)

    ports = container.resolve(PlanningPorts)

    mock_config.get_setting.side_effect = lambda key, default=None: (
        3 if key == "llm.max_retries" else default
    )

    success_choice = POSIXPathMock()
    success_choice.message.content = "# Plan\nContent"
    success_response = POSIXPathMock()
    success_response.choices = [success_choice]

    mock_llm.get_completion.return_value = success_response
    mock_llm.get_completion_cost.return_value = 0.25

    service = PlanningService(ports)

    # Act
    _, _, turn_cost = service._perform_generation_with_retry(
        messages=[], model="test-model"
    )

    # Assert
    assert mock_llm.get_completion.call_count == 1
    assert mock_llm.get_completion_cost.call_count == 1
    assert turn_cost == pytest.approx(0.25)
