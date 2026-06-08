"""Regression test for Bug #18: Model Display Line Redundancy.

Verifies that the PlanningService does NOT emit a separate "• Actual model:"
line after the LLM response. The actual model should be persisted in meta.yaml
and displayed via the standard "• Model:" telemetry on subsequent turns.
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


def test_no_actual_model_line_emitted(env):
    """The planning service should not emit a dedicated 'Actual model' line."""
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
    mock_prompt.resolve_agent_metadata.return_value = (
        "pathfinder",
        {"cumulative_cost": 0.0, "model": "input-model"},
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

    # Assert: No message contains "Actual model"
    for msg in messages:
        assert "Actual model" not in msg, (
            f"Found redundant 'Actual model' message: {msg}"
        )
