from unittest.mock import MagicMock
from punq import Container
from teddy_executor.adapters.inbound.session_cli_handlers import handle_new_session
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase


def test_handle_new_session_prompts_for_message_before_creating_dir():
    # Arrange
    container = Container()
    mock_session_manager = MagicMock(spec=ISessionManager)
    mock_user_interactor = MagicMock(spec=IUserInteractor)
    mock_orchestrator = MagicMock(spec=IRunPlanUseCase)

    container.register(ISessionManager, instance=mock_session_manager)
    container.register(IUserInteractor, instance=mock_user_interactor)
    container.register(IRunPlanUseCase, instance=mock_orchestrator)

    # Set up call order tracking
    manager = MagicMock()
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

    # 3. Correct name used (slugified from prompt)
    mock_session_manager.create_session.assert_called_once_with(
        name="build-rocket",  # slugify("Build a rocket") -> "build-rocket"
        agent_name="pathfinder",
    )
