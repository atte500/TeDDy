from unittest.mock import Mock
from punq import Container
from teddy_executor.adapters.inbound.session_cli_handlers import handle_new_session
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.domain.models.session import SessionOptions
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.session_loop_guard import ISessionLoopGuard


def test_handle_new_session_prompts_for_message_before_creating_dir():
    # Arrange
    container = Container()
    mock_session_manager = Mock(spec=ISessionManager)
    mock_user_interactor = Mock(spec=IUserInteractor)
    mock_orchestrator = Mock(spec=IRunPlanUseCase)
    mock_llm_client = Mock(spec=ILlmClient)
    mock_config_service = Mock(spec=IConfigService)
    mock_loop_guard = Mock(spec=ISessionLoopGuard)

    container.register(IInitUseCase, instance=Mock(spec=IInitUseCase))
    container.register(ISessionManager, instance=mock_session_manager)
    container.register(IUserInteractor, instance=mock_user_interactor)
    container.register(IRunPlanUseCase, instance=mock_orchestrator)
    container.register(ILlmClient, instance=mock_llm_client)
    container.register(IConfigService, instance=mock_config_service)
    container.register(ISessionLoopGuard, instance=mock_loop_guard)

    # Default: valid config
    mock_llm_client.validate_config.return_value = []

    # Set up call order tracking
    manager = Mock()
    manager.attach_mock(mock_user_interactor.ask_question, "ask_question")
    manager.attach_mock(mock_session_manager.create_session, "create_session")

    mock_user_interactor.ask_question.return_value = "Build a rocket"
    mock_session_manager.create_session.return_value = (
        ".teddy/sessions/20260427_110000-build-a-rocket"
    )
    mock_orchestrator.resume.return_value = None  # Stop loop

    # Act
    handle_new_session(
        container=container,
        name=None,
        agent="pathfinder",
        interactive=True,
        no_copy=False,
        message=None,
    )

    # Assert
    # 1. Prompt was shown
    mock_user_interactor.ask_question.assert_called_once()

    # 2. Sequence: ask_question -> create_session
    # We use manager.mock_calls for strict ordering
    call_names = [call[0] for call in manager.mock_calls]
    assert call_names == ["ask_question", "create_session"], (
        f"Wrong sequence: {call_names}"
    )

    # 3. Correct name used (slugified from prompt) and initial request seeded
    mock_session_manager.create_session.assert_called_once_with(
        SessionOptions(
            name="build-rocket",
            agent_name="pathfinder",
            initial_request="Build a rocket",
            additional_context=[],
        )
    )


def test_handle_new_session_prompts_even_when_non_interactive():
    # Arrange
    container = Container()
    mock_session_manager = Mock(spec=ISessionManager)
    mock_user_interactor = Mock(spec=IUserInteractor)
    mock_orchestrator = Mock(spec=IRunPlanUseCase)
    mock_llm_client = Mock(spec=ILlmClient)
    mock_config_service = Mock(spec=IConfigService)
    mock_loop_guard = Mock(spec=ISessionLoopGuard)

    container.register(IInitUseCase, instance=Mock(spec=IInitUseCase))
    container.register(ISessionManager, instance=mock_session_manager)
    container.register(IUserInteractor, instance=mock_user_interactor)
    container.register(IRunPlanUseCase, instance=mock_orchestrator)
    container.register(ILlmClient, instance=mock_llm_client)
    container.register(IConfigService, instance=mock_config_service)
    container.register(ISessionLoopGuard, instance=mock_loop_guard)

    mock_llm_client.validate_config.return_value = []
    mock_user_interactor.ask_question.return_value = "Do something non-interactive"
    mock_session_manager.create_session.return_value = ".teddy/sessions/something"
    mock_orchestrator.resume.return_value = None

    # Act
    handle_new_session(
        container=container,
        name=None,
        agent="pathfinder",
        interactive=False,
        no_copy=False,
        message=None,
    )

    # Assert
    mock_user_interactor.ask_question.assert_called_once_with("What are we working on?")
    mock_session_manager.create_session.assert_called_once_with(
        SessionOptions(
            name="something-non-interactive",
            agent_name="pathfinder",
            initial_request="Do something non-interactive",
            additional_context=[],
        )
    )


def test_handle_new_session_raises_eof_error_on_empty_prompt_response_in_non_interactive():
    import pytest
    import typer

    # Arrange
    container = Container()
    mock_session_manager = Mock(spec=ISessionManager)
    mock_user_interactor = Mock(spec=IUserInteractor)
    mock_llm_client = Mock(spec=ILlmClient)
    mock_config_service = Mock(spec=IConfigService)

    container.register(IInitUseCase, instance=Mock(spec=IInitUseCase))
    container.register(ISessionManager, instance=mock_session_manager)
    container.register(IUserInteractor, instance=mock_user_interactor)
    container.register(ILlmClient, instance=mock_llm_client)
    container.register(IConfigService, instance=mock_config_service)

    mock_llm_client.validate_config.return_value = []
    # Simulate EOF / Empty response from closed stdin
    mock_user_interactor.ask_question.return_value = ""

    # Act & Assert
    with pytest.raises(typer.Exit) as excinfo:
        handle_new_session(
            container=container,
            name=None,
            agent="pathfinder",
            interactive=False,
            no_copy=False,
            message=None,
        )

    assert excinfo.value.exit_code == 1
    mock_session_manager.create_session.assert_not_called()
