import pytest
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.outbound import (
    ILlmClient,
    IConfigService,
    IFileSystemManager,
    IUserInteractor,
    ISessionManager,
)
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.services.planning_service import PlanningService
from teddy_executor.core.domain.models.exceptions import ConfigurationError


def test_generate_plan_raises_configuration_error_on_invalid_config(env):
    # Arrange
    mock_llm = env.mock_port(ILlmClient)
    mock_llm.validate_config.return_value = ["Missing GOOGLE_API_KEY"]

    mock_config = env.mock_port(IConfigService)
    mock_config.get_config_path.return_value = ".teddy/config.yaml"

    env.mock_port(IGetContextUseCase)
    env.mock_port(IFileSystemManager)
    env.mock_port(IUserInteractor)
    env.mock_port(ISessionManager)
    mock_prompt = env.mock_port(IPromptManager)

    mock_prompt.resolve_message.return_value = "do something"
    mock_prompt.resolve_agent_metadata.return_value = ("developer", {}, "meta.yaml")

    service = env.get_service(PlanningService)

    # Act / Assert
    with pytest.raises(ConfigurationError) as exc_info:
        service.generate_plan(user_message="test message", turn_dir="sessions/turn1")

    # Verify the error message contains the expected details
    # Note: Resolution paths are now handled by the CLI layer, not the service.
    assert "Configuration Error" in str(exc_info.value)
    assert "Missing GOOGLE_API_KEY" in str(exc_info.value)

    # Verify the LLM was NOT called for completion
    mock_llm.get_completion.assert_not_called()
