"""Regression test for Bug #18: Model Display Resolution.

Verifies that the PlanningService displays the actual_model value in the
standard "• Model:" telemetry line when actual_model is available in meta.yaml,
falling back to the model value when actual_model is absent.
"""

from unittest.mock import Mock
from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.domain.models.planning_ports import PlanningPorts
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


def test_telemetry_shows_actual_model_when_available(env):
    """When actual_model is in meta.yaml, the "• Model:" telemetry should show it."""
    # Arrange
    mock_ui = env.mock_port(IUserInteractor)
    mock_llm = env.mock_port(ILlmClient)
    mock_prompt = env.mock_port(IPromptManager)
    mock_context = env.mock_port(IGetContextUseCase)
    mock_fs = env.mock_port(IFileSystemManager)

    mock_context.get_context.return_value = ProjectContext(
        header="H", content="C", scoped_paths={}
    )

    mock_response = Mock()
    mock_response.model = "deepseek/deepseek-v4-20260423"
    choice = Mock()
    choice.message.content = "# Plan\nSome content"
    mock_response.choices = [choice]

    mock_llm.get_completion.return_value = mock_response
    mock_llm.get_completion_cost.return_value = 0.001
    mock_llm.get_token_count.return_value = 500
    mock_llm.get_context_window.return_value = 128000
    mock_llm.supports_pricing.return_value = True

    mock_prompt.resolve_message.return_value = "test"
    # Provide actual_model in meta to simulate a resumed turn with history
    mock_prompt.resolve_agent_metadata.return_value = (
        "pathfinder",
        {
            "cumulative_cost": 0.0,
            "model": "deepseek-chat",
            "actual_model": "deepseek/deepseek-v4-20260423",
        },
        "meta.yaml",
    )
    mock_prompt.fetch_system_prompt.return_value = "system-prompt"
    mock_prompt.log_telemetry.return_value = 0.001

    mock_fs.path_exists.return_value = True

    # Register PlanningService with the env via its ports DTO
    env.container.register(
        PlanningPorts,
        factory=lambda: PlanningPorts(
            context=mock_context,
            llm=mock_llm,
            fs=mock_fs,
            config=env.mock_port(IConfigService),
            prompts=mock_prompt,
            ui=mock_ui,
            session_manager=env.mock_port(ISessionManager),
        ),
    )
    env.container.register(PlanningService)
    service = env.get_service(PlanningService)

    # Capture display messages
    messages = []
    mock_ui.display_message.side_effect = lambda msg: messages.append(msg)

    # Act
    service.generate_plan(user_message="test", turn_dir="turns/01")

    # Assert: The "• Model:" line shows actual_model, not the user-configured model
    model_line = None
    for msg in messages:
        if "• Model:" in msg:
            model_line = msg
            break
    assert model_line is not None, "Expected a '• Model:' telemetry line"
    assert "deepseek/deepseek-v4-20260423" in model_line, (
        f"Expected actual_model in telemetry, got: {model_line}"
    )


def test_telemetry_falls_back_to_model_when_actual_model_absent(env):
    """When actual_model is NOT in meta.yaml, the "• Model:" telemetry should show model."""
    # Arrange
    mock_ui = env.mock_port(IUserInteractor)
    mock_llm = env.mock_port(ILlmClient)
    mock_prompt = env.mock_port(IPromptManager)
    mock_context = env.mock_port(IGetContextUseCase)
    mock_fs = env.mock_port(IFileSystemManager)

    mock_context.get_context.return_value = ProjectContext(
        header="H", content="C", scoped_paths={}
    )

    mock_response = Mock()
    mock_response.model = "deepseek/deepseek-v4-20260423"
    choice = Mock()
    choice.message.content = "# Plan\nSome content"
    mock_response.choices = [choice]

    mock_llm.get_completion.return_value = mock_response
    mock_llm.get_completion_cost.return_value = 0.001
    mock_llm.get_token_count.return_value = 500
    mock_llm.get_context_window.return_value = 128000
    mock_llm.supports_pricing.return_value = True

    mock_prompt.resolve_message.return_value = "test"
    # No actual_model in meta — simulates first turn or turn without execution history
    mock_prompt.resolve_agent_metadata.return_value = (
        "pathfinder",
        {"cumulative_cost": 0.0, "model": "deepseek-chat"},
        "meta.yaml",
    )
    mock_prompt.fetch_system_prompt.return_value = "system-prompt"
    mock_prompt.log_telemetry.return_value = 0.001

    mock_fs.path_exists.return_value = True

    # Register PlanningService with the env via its ports DTO
    env.container.register(
        PlanningPorts,
        factory=lambda: PlanningPorts(
            context=mock_context,
            llm=mock_llm,
            fs=mock_fs,
            config=env.mock_port(IConfigService),
            prompts=mock_prompt,
            ui=mock_ui,
            session_manager=env.mock_port(ISessionManager),
        ),
    )
    env.container.register(PlanningService)
    service = env.get_service(PlanningService)

    # Capture display messages
    messages = []
    mock_ui.display_message.side_effect = lambda msg: messages.append(msg)

    # Act
    service.generate_plan(user_message="test", turn_dir="turns/01")

    # Assert: The "• Model:" line shows the fallback model value
    model_line = None
    for msg in messages:
        if "• Model:" in msg:
            model_line = msg
            break
    assert model_line is not None, "Expected a '• Model:' telemetry line"
    assert "deepseek-chat" in model_line, (
        f"Expected model fallback in telemetry, got: {model_line}"
    )
    # Verify actual_model is NOT in the telemetry (since it wasn't in meta)
    assert "deepseek/deepseek-v4-20260423" not in model_line, (
        "Telemetry should NOT show actual_model when it's absent from meta"
    )
