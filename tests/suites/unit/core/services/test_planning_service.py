import pytest
from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.domain.models.planning_ports import PlanningPorts
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.outbound import (
    ILlmClient,
    IConfigService,
    IFileSystemManager,
    IUserInteractor,
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
        ),
    )
    env.container.register(PlanningService)
    return env.get_service(PlanningService)


def test_generate_plan_uses_model_from_config(env):
    # Arrange - Configure mocks BEFORE resolving the service
    mock_config = env.mock_port(IConfigService)
    mock_prompt_manager = env.mock_port(IPromptManager)
    mock_llm_client = env.mock_port(ILlmClient)
    mock_context_service = env.mock_port(IGetContextUseCase)

    # Resolve service AFTER mocking to ensure injection parity
    from teddy_executor.core.services.planning_service import PlanningService

    service = env.get_service(PlanningService)

    mock_config.get_setting.return_value = "config-specified-model"
    mock_prompt_manager.resolve_message.return_value = "test"
    mock_prompt_manager.resolve_agent_metadata.return_value = (
        "pathfinder",
        {},
        "meta.yaml",
    )
    mock_prompt_manager.fetch_system_prompt.return_value = "prompt"
    mock_context_service.get_context.return_value = ProjectContext(
        header="H", content="C", scoped_paths={}, git_status=""
    )

    # Act
    service.generate_plan(user_message="test", turn_dir="01")

    # Assert
    assert mock_llm_client.get_completion.called
    actual_model = mock_llm_client.get_completion.call_args.kwargs["model"]
    assert actual_model == "config-specified-model"


def test_generate_plan_uses_fallback_model_if_not_in_config(env):
    # Arrange
    mock_config = env.mock_port(IConfigService)
    mock_prompt_manager = env.mock_port(IPromptManager)
    mock_llm_client = env.mock_port(ILlmClient)
    mock_context_service = env.mock_port(IGetContextUseCase)

    from teddy_executor.core.services.planning_service import PlanningService

    service = env.get_service(PlanningService)

    mock_config.get_setting.return_value = None
    mock_prompt_manager.resolve_message.return_value = "test"
    mock_prompt_manager.resolve_agent_metadata.return_value = (
        "pathfinder",
        {},
        "meta.yaml",
    )
    mock_prompt_manager.fetch_system_prompt.return_value = "prompt"
    mock_context_service.get_context.return_value = ProjectContext(
        header="H", content="C", scoped_paths={}, git_status=""
    )

    # Act
    service.generate_plan(user_message="test", turn_dir="01")

    # Assert
    assert mock_llm_client.get_completion.called
    actual_model = mock_llm_client.get_completion.call_args.kwargs["model"]
    assert actual_model == "gpt-4o"


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
