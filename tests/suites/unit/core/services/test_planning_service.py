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
    assert "test-message" in messages[1]["content"]
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


def test_generate_plan_injects_user_request_in_input_md_on_first_turn(env):
    # Arrange
    mock_context_service = env.mock_port(IGetContextUseCase)
    mock_fs = env.mock_port(IFileSystemManager)
    mock_prompt_manager = env.mock_port(IPromptManager)
    env.mock_port(ILlmClient)

    from teddy_executor.core.services.planning_service import PlanningService

    service = env.get_service(PlanningService)

    mock_context_service.get_context.return_value = ProjectContext(
        header="# Project Context\n## 1. System Information\n- Info",
        content="## 2. Git Status\nClean",
        scoped_paths={},
    )
    mock_prompt_manager.resolve_message.return_value = "I want to build a rocket."
    mock_prompt_manager.resolve_agent_metadata.return_value = (
        "pathfinder",
        {},
        "meta.yaml",
    )
    mock_prompt_manager.fetch_system_prompt.return_value = "prompt"

    # Act
    # Turn "01" triggers injection
    service.generate_plan(user_message="test", turn_dir="turns/01")

    # Assert
    input_call = [
        c for c in mock_fs.write_file.call_args_list if "input.md" in c[0][0]
    ][0]
    input_content = input_call[0][1]

    assert "## User Request" in input_content
    assert "~~~~~~text\nI want to build a rocket.\n~~~~~~" in input_content
    # Verify placement: should be after System Information (the header)
    assert input_content.startswith(
        "# Project Context\n## 1. System Information\n- Info\n\n## User Request"
    )


def test_generate_plan_does_not_inject_user_request_on_subsequent_turns(env):
    # Arrange
    mock_context_service = env.mock_port(IGetContextUseCase)
    mock_fs = env.mock_port(IFileSystemManager)
    mock_prompt_manager = env.mock_port(IPromptManager)
    env.mock_port(ILlmClient)

    from teddy_executor.core.services.planning_service import PlanningService

    service = env.get_service(PlanningService)

    mock_context_service.get_context.return_value = ProjectContext(
        header="# Project Context\n## 1. System Information\n- Info",
        content="## 2. Git Status\nClean",
        scoped_paths={},
    )
    mock_prompt_manager.resolve_message.return_value = "More rocket parts."
    mock_prompt_manager.resolve_agent_metadata.return_value = (
        "pathfinder",
        {},
        "meta.yaml",
    )
    mock_prompt_manager.fetch_system_prompt.return_value = "prompt"

    # Act
    # Turn "02" does NOT trigger injection
    service.generate_plan(user_message="test", turn_dir="turns/02")

    # Assert
    input_call = [
        c for c in mock_fs.write_file.call_args_list if "input.md" in c[0][0]
    ][0]
    input_content = input_call[0][1]

    assert "## User Request" not in input_content
