import pytest
from unittest.mock import MagicMock
from teddy_executor.core.services.planning_service import PlanningService
from teddy_executor.core.domain.models.planning_ports import PlanningPorts
from teddy_executor.core.domain.models.exceptions import ConfigurationError


def test_generate_plan_raises_configuration_error_on_invalid_config():
    # Arrange
    # We use a mock for the ports and dependencies
    mock_llm = MagicMock()
    mock_llm.validate_config.return_value = ["Missing GOOGLE_API_KEY"]

    mock_config = MagicMock()
    mock_config.get_config_path.return_value = ".teddy/config.yaml"

    # We need a minimal ports DTO
    ports = MagicMock(spec=PlanningPorts)
    ports.llm = mock_llm
    ports.config = mock_config
    ports.context = MagicMock()
    ports.fs = MagicMock()
    ports.prompts = MagicMock()
    ports.ui = MagicMock()

    # Mock prompt manager to avoid resolving metadata/agent
    ports.prompts.resolve_message.return_value = "do something"
    ports.prompts.resolve_agent_metadata.return_value = ("developer", {}, "meta.yaml")

    service = PlanningService(ports)

    # Act / Assert
    with pytest.raises(ConfigurationError) as exc_info:
        service.generate_plan(user_message="test message", turn_dir="sessions/turn1")

    # Verify the error message contains the expected details
    assert "Configuration Error" in str(exc_info.value)
    assert "Missing GOOGLE_API_KEY" in str(exc_info.value)
    assert ".teddy/config.yaml" in str(exc_info.value)

    # Verify the LLM was NOT called for completion
    mock_llm.get_completion.assert_not_called()
