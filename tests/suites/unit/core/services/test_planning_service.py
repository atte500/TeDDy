import pytest
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


@pytest.fixture
def service(env):
    # Ensure PlanningService and its ports DTO are registered
    env.container.register(
        PlanningPorts,
        factory=lambda: PlanningPorts(
            context=env.container.resolve(IGetContextUseCase),
            llm=env.container.resolve(ILlmClient),
            fs=env.container.resolve(IFileSystemManager),
            config=env.container.resolve(IConfigService),
            prompts=env.container.resolve(IPromptManager),
            ui=env.container.resolve(IUserInteractor),
            session_manager=env.container.resolve(ISessionManager),
        ),
    )
    env.container.register(PlanningService)
    return env.get_service(PlanningService)


def test_generate_plan_delegates_to_llm_client(env):
    # Arrange
    mock_prompt_manager = env.mock_port(IPromptManager)
    mock_llm_client = env.mock_port(ILlmClient)
    mock_context_service = env.mock_port(IGetContextUseCase)

    from teddy_executor.core.services.planning_service import PlanningService

    service = env.get_service(PlanningService)

    mock_prompt_manager.resolve_message.return_value = "test-message"
    mock_prompt_manager.resolve_agent_metadata.return_value = (
        "pathfinder",
        {},
        "meta.yaml",
    )
    mock_prompt_manager.fetch_system_prompt.return_value = "system-prompt"
    mock_context_service.get_context.return_value = ProjectContext(
        header="H", content="C", scoped_paths={}, git_status=""
    )

    # Act
    service.generate_plan(user_message="test", turn_dir="01")

    # Assert
    # Verify the service calls completion with the expected messages,
    # but NO longer specifies a model (decoupling for pass-through).
    assert mock_llm_client.get_completion.called
    args, kwargs = mock_llm_client.get_completion.call_args
    assert "messages" in kwargs
    messages = kwargs["messages"]
    assert messages[0]["content"] == "system-prompt"
    # Pure context strategy: user message is context only
    assert messages[1]["content"] == "H\nC"
    assert "model" not in kwargs  # Handled by Adapter/Config now


def test_generate_plan_writes_standardized_input_md(env):
    # Arrange
    mock_context_service = env.mock_port(IGetContextUseCase)
    mock_fs = env.mock_port(IFileSystemManager)
    mock_prompt_manager = env.mock_port(IPromptManager)
    env.mock_port(ILlmClient)  # Register for injection

    from teddy_executor.core.services.planning_service import PlanningService

    service = env.get_service(PlanningService)

    mock_context_service.get_context.return_value = ProjectContext(
        header="Expected Header",
        content="Expected Content",
        scoped_paths={},
        git_status="",
    )
    mock_prompt_manager.resolve_message.return_value = "test"
    mock_prompt_manager.resolve_agent_metadata.return_value = (
        "pathfinder",
        {},
        "meta.yaml",
    )
    mock_prompt_manager.fetch_system_prompt.return_value = "prompt"

    # Act
    service.generate_plan(user_message="test", turn_dir="turns/01")

    # Assert
    # Verify input.md contains the simplified context
    input_call = [
        c for c in mock_fs.write_file.call_args_list if "input.md" in c[0][0]
    ][0]
    input_content = input_call[0][1]
    assert "Expected Header" in input_content
    assert "Expected Content" in input_content


def test_generate_plan_displays_telemetry_before_llm_call(env):
    # Arrange
    mock_ui = env.mock_port(IUserInteractor)
    mock_llm = env.mock_port(ILlmClient)
    mock_prompt = env.mock_port(IPromptManager)
    env.mock_port(IGetContextUseCase).get_context.return_value = ProjectContext(
        header="H", content="C", scoped_paths={}
    )

    mock_prompt.resolve_message.return_value = "test"
    mock_prompt.resolve_agent_metadata.return_value = (
        "pathfinder",
        {"cumulative_cost": 0.05, "model": "gpt-4o"},
        "meta.yaml",
    )
    mock_llm.get_token_count.return_value = 1200
    mock_llm.get_context_window.return_value = 128000

    from teddy_executor.core.services.planning_service import PlanningService

    service = env.get_service(PlanningService)

    # Act
    service.generate_plan(user_message="test", turn_dir="turns/01")

    # Assert
    # Verify telemetry calls. We look for the context and cost strings specifically.
    calls = [call[0][0] for call in mock_ui.display_message.call_args_list]

    # Telemetry should be displayed
    assert any("• Model:" in c and "gpt-4o" in c for c in calls)
    assert any("• Context:" in c and "1.2k / 128.0k tokens" in c for c in calls)
    assert any("• Session Cost:" in c and "$0.0500" in c for c in calls)


def test_planning_service_has_session_manager(env):
    """Verify that PlanningService has the session manager injected."""
    from teddy_executor.core.services.planning_service import PlanningService

    service = env.get_service(PlanningService)
    assert hasattr(service, "_session_manager")
