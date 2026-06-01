from typing import Any
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
