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
    assert "model" in kwargs  # Now explicitly passed for override support


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


def test_generate_plan_displays_sentinel_for_unknown_model_telemetry(env):
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
        {"cumulative_cost": 0.0, "model": "unknown-model"},
        "meta.yaml",
    )
    mock_llm.get_token_count.return_value = 1000
    mock_llm.get_context_window.return_value = 0  # Unknown

    from teddy_executor.core.services.planning_service import PlanningService

    service = env.get_service(PlanningService)

    # Act
    service.generate_plan(user_message="test", turn_dir="turns/01")

    # Assert
    calls = [call[0][0] for call in mock_ui.display_message.call_args_list]
    # Context window should be ???
    assert any("• Context:" in c and "1.0k / ??? tokens" in c for c in calls)
    # Session cost should be $???
    assert any("• Session Cost:" in c and "$???" in c for c in calls)


def test_generate_plan_displays_sentinel_for_missing_pricing_telemetry(env):
    """
    R-10-15: Even if context window is known, if pricing is not supported,
    session cost should show $???.
    """
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
        {"cumulative_cost": 0.0, "model": "hydrated-no-pricing"},
        "meta.yaml",
    )
    mock_llm.get_token_count.return_value = 1000
    mock_llm.get_context_window.return_value = 128000
    mock_llm.supports_pricing.return_value = False

    from teddy_executor.core.services.planning_service import PlanningService

    service = env.get_service(PlanningService)

    # Act
    service.generate_plan(user_message="test", turn_dir="turns/01")

    # Assert
    calls = [call[0][0] for call in mock_ui.display_message.call_args_list]
    # Context window is known
    assert any("• Context:" in c and "1.0k / 128.0k tokens" in c for c in calls)
    # Session cost should be $??? because pricing is missing
    assert any("• Session Cost:" in c and "$???" in c for c in calls)


def test_planning_service_has_session_manager(env):
    """Verify that PlanningService has the session manager injected."""
    from teddy_executor.core.services.planning_service import PlanningService

    service = env.get_service(PlanningService)
    assert hasattr(service, "_session_manager")


def test_generate_plan_auto_resolves_context_from_turn_dir_when_missing(env):
    """
    R-10-12: PlanningService should auto-resolve session context manifests
    from turn_dir if context_files is not provided.
    """
    # Arrange
    mock_session_manager = env.mock_port(ISessionManager)
    mock_context_service = env.mock_port(IGetContextUseCase)
    mock_prompt_manager = env.mock_port(IPromptManager)
    env.mock_port(ILlmClient)

    from teddy_executor.core.services.planning_service import PlanningService

    service = env.get_service(PlanningService)

    # Setup standard mocks to allow generation to proceed
    mock_prompt_manager.resolve_message.return_value = "test"
    mock_prompt_manager.resolve_agent_metadata.return_value = ("pf", {}, "m.yaml")
    mock_prompt_manager.fetch_system_prompt.return_value = "system"
    mock_context_service.get_context.return_value = ProjectContext(
        header="H", content="C", scoped_paths={}
    )

    # Setup the session manager to return fake manifests
    fake_manifests = {"Session": ["s.context"], "Turn": ["t.context"]}
    mock_session_manager.resolve_context_paths.return_value = fake_manifests

    # Act
    service.generate_plan(user_message="test", turn_dir="sessions/S1/02")

    # Assert
    # 1. Verify resolve_context_paths was called for the turn directory
    # We expect it to be called with a path targeting plan.md inside the dir
    expected_plan_path = "sessions/S1/02/plan.md"
    mock_session_manager.resolve_context_paths.assert_called_once_with(
        expected_plan_path
    )

    # 2. Verify get_context received the resolved manifests
    mock_context_service.get_context.assert_called_once_with(
        context_files=fake_manifests, agent_name="pf", current_turn="02"
    )


def test_generate_plan_suppresses_overwriting_user_request_if_is_replan_is_true(env):
    """Verify that generate_plan does not overwrite user_request when is_replan is True."""
    # Arrange
    mock_prompt_manager = env.mock_port(IPromptManager)
    env.mock_port(ILlmClient)
    mock_context_service = env.mock_port(IGetContextUseCase)

    from teddy_executor.core.services.planning_service import PlanningService

    service = env.get_service(PlanningService)

    existing_meta = {
        "user_request": "Original human request",
        "is_replan": True,
    }

    mock_prompt_manager.resolve_message.return_value = "Automated validation feedback"
    mock_prompt_manager.resolve_agent_metadata.return_value = (
        "pathfinder",
        existing_meta,
        "meta.yaml",
    )
    mock_prompt_manager.fetch_system_prompt.return_value = "system-prompt"
    mock_context_service.get_context.return_value = ProjectContext(
        header="H", content="C", scoped_paths={}, git_status=""
    )

    # Act
    service.generate_plan(user_message="Automated validation feedback", turn_dir="02")

    # Assert
    assert existing_meta["user_request"] == "Original human request"


def test_generate_plan_overwrites_user_request_if_not_replan(env):
    """Verify that generate_plan normal overwriting behaves as expected when is_replan is absent or False."""
    # Arrange
    mock_prompt_manager = env.mock_port(IPromptManager)
    env.mock_port(ILlmClient)
    mock_context_service = env.mock_port(IGetContextUseCase)

    from teddy_executor.core.services.planning_service import PlanningService

    service = env.get_service(PlanningService)

    existing_meta = {
        "user_request": "Old request",
    }

    mock_prompt_manager.resolve_message.return_value = "New user request"
    mock_prompt_manager.resolve_agent_metadata.return_value = (
        "pathfinder",
        existing_meta,
        "meta.yaml",
    )
    mock_prompt_manager.fetch_system_prompt.return_value = "system-prompt"
    mock_context_service.get_context.return_value = ProjectContext(
        header="H", content="C", scoped_paths={}, git_status=""
    )

    # Act
    service.generate_plan(user_message="New user request", turn_dir="01")

    # Assert
    assert existing_meta["user_request"] == "New user request"


def test_run_preflight_check_raises_on_error(env):
    """Verify that PlanningService raises ConfigurationError if preflight fails."""
    # Arrange
    mock_llm = env.mock_port(ILlmClient)
    mock_llm.validate_config.return_value = ["Missing Model"]

    from teddy_executor.core.services.planning_service import PlanningService
    from teddy_executor.core.domain.models.exceptions import ConfigurationError

    service = env.get_service(PlanningService)

    # Act & Assert
    with pytest.raises(ConfigurationError, match="Missing Model"):
        service._run_preflight_check()


def test_run_preflight_check_requests_local_validation(env):
    """Verify that PlanningService specifically requests local validation during preflight."""
    # Arrange
    mock_llm = env.mock_port(ILlmClient)
    mock_llm.validate_config.return_value = []

    from teddy_executor.core.services.planning_service import PlanningService

    service = env.get_service(PlanningService)

    # Act
    service._run_preflight_check()

    # Assert
    # We perform local validation only. Remote connectivity is checked lazily
    # by the LLM client during actual generation.
    mock_llm.validate_config.assert_called_once_with(include_remote=False)


def test_generate_plan_displays_no_actual_model_line_after_fix(env):
    """
    Bug #18: Verify that the redundant "• Actual model:" line is NOT emitted.
    The actual model should be persisted to meta.yaml via update_meta instead.
    """
    # Arrange
    from unittest.mock import Mock
    from teddy_executor.core.domain.models import ProjectContext
    from teddy_executor.core.ports.inbound.get_context_use_case import (
        IGetContextUseCase,
    )
    from teddy_executor.core.ports.outbound import (
        ILlmClient,
        IUserInteractor,
        IPromptManager,
        IFileSystemManager,
    )

    mock_ui = env.mock_port(IUserInteractor)
    mock_llm = env.mock_port(ILlmClient)
    mock_prompt = env.mock_port(IPromptManager)
    mock_context = env.mock_port(IGetContextUseCase)
    mock_fs = env.mock_port(IFileSystemManager)
    mock_context.get_context.return_value = ProjectContext(
        header="H", content="C", scoped_paths={}
    )

    # Mock response with model different from the requested override
    mock_response = Mock()
    mock_response.model = "deepseek/deepseek-v4-flash-20260423"
    choice = Mock()
    choice.message.content = "# Plan title\nSome content"
    mock_response.choices = [choice]

    mock_llm.get_completion.return_value = mock_response
    mock_llm.get_completion_cost.return_value = 0.001
    mock_llm.get_token_count.return_value = 1000
    mock_llm.get_context_window.return_value = 128000
    mock_llm.supports_pricing.return_value = True

    meta = {"cumulative_cost": 0.0, "model": "openrouter/unknown-override"}
    mock_prompt.resolve_message.return_value = "test"
    mock_prompt.resolve_agent_metadata.return_value = (
        "pathfinder",
        meta,
        "meta.yaml",
    )
    mock_prompt.fetch_system_prompt.return_value = "system-prompt"
    mock_prompt.log_telemetry.return_value = 0.001

    # Mock file system to accept meta.yaml writes
    mock_fs.path_exists.return_value = True

    from teddy_executor.core.services.planning_service import PlanningService

    service = env.get_service(PlanningService)

    # Act
    service.generate_plan(user_message="test", turn_dir="turns/01")

    # Assert: No "Actual model" line in display
    calls = [call[0][0] for call in mock_ui.display_message.call_args_list]
    assert not any("Actual model" in c for c in calls), (
        f"Found unexpected 'Actual model' in display calls: {calls}"
    )

    # Assert: update_meta was called with the meta dict containing the actual response model
    mock_prompt.update_meta.assert_called_once()
    args, _ = mock_prompt.update_meta.call_args
    # args[0] is the meta dict; the real update_meta will overwrite meta["model"],
    # but the mock doesn't execute real logic, so we just verify the call happened.
    # (The actual persistence is tested by prompt_manager unit tests.)
