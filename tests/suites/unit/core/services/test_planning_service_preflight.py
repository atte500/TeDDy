from typing import Any, Dict

import pytest
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
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
from teddy_executor.core.domain.models.planning_ports import PlanningPorts
from tests.harness.setup.litellm_doubles import FakeLitellmProvider


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


def test_preflight_rejects_truthy_stream_before_completion_or_plan_write(env):
    """The real adapter's `llm.stream` guard reaches the service boundary.

    The first test stubs `validate_config` with an arbitrary list, so it proves
    the seam raises but not that the real guard travels through it. This one
    injects a real `LiteLLMAdapter` over a recording provider double and asserts
    the whole boundary: preflight raises, no completion request is issued, and
    no plan file is written.
    """
    mock_config = env.mock_port(IConfigService)
    mock_fs = env.mock_port(IFileSystemManager)
    mock_prompt_manager = env.mock_port(IPromptManager)
    mock_user_interactor = env.mock_port(IUserInteractor)
    mock_context_service = env.mock_port(IGetContextUseCase)
    mock_session_manager = env.mock_port(ISessionManager)
    mock_prompt_manager.resolve_agent_metadata.return_value = (
        "developer",
        {},
        "meta.yaml",
    )
    mock_prompt_manager.resolve_message.return_value = "do something"
    provider = FakeLitellmProvider()
    settings: Dict[str, Any] = {
        "llm.model": "gpt-4o",
        "llm.api_key": "sk-test",  # pragma: allowlist secret
        "llm.stream": True,
        "llm": {},
        "agents": {},
    }
    mock_config.get_setting.side_effect = lambda key, default=None: settings.get(
        key, default
    )

    service = PlanningService(
        ports=PlanningPorts(
            context=mock_context_service,
            llm=LiteLLMAdapter(config_service=mock_config, _litellm_provider=provider),
            fs=mock_fs,
            config=mock_config,
            prompts=mock_prompt_manager,
            ui=mock_user_interactor,
            session_manager=mock_session_manager,
        )
    )

    with pytest.raises(ConfigurationError, match="llm.stream"):
        service.generate_plan(
            user_message="do something",
            turn_dir="sessions/0001",
            context_files={},
        )

    assert provider.completion_calls == []
    mock_fs.write_file.assert_not_called()
