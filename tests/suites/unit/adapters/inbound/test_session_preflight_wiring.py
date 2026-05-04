import pytest
from unittest.mock import MagicMock
import typer
from punq import Container
from teddy_executor.adapters.inbound.session_cli_handlers import (
    handle_new_session,
    handle_resume_session,
    handle_plan_generation,
)
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.config_service import IConfigService


def test_handle_new_session_halts_on_preflight_failure_before_prompt():
    # Arrange
    container = Container()
    mock_session_manager = MagicMock(spec=ISessionManager)
    mock_user_interactor = MagicMock(spec=IUserInteractor)
    mock_llm_client = MagicMock(spec=ILlmClient)
    mock_config_service = MagicMock(spec=IConfigService)

    container.register(ISessionManager, instance=mock_session_manager)
    container.register(IUserInteractor, instance=mock_user_interactor)
    container.register(ILlmClient, instance=mock_llm_client)
    container.register(IConfigService, instance=mock_config_service)

    # Set up preflight failure
    mock_llm_client.validate_config.return_value = ["API Key is placeholder"]
    mock_config_service.get_config_path.return_value = ".teddy/config.yaml"

    # Act & Assert
    # We expect a typer.Exit(1) due to the error handling in the handler
    with pytest.raises(typer.Exit) as excinfo:
        handle_new_session(
            container=container,
            name=None,
            agent="pathfinder",
            interactive=True,
            no_copy=False,
            message=None,
        )

    # Verify exit code
    assert excinfo.value.exit_code == 1

    # Assert: User was NEVER prompted because preflight failed first
    mock_user_interactor.ask_question.assert_not_called()
    # Assert: Session was NEVER created
    mock_session_manager.create_session.assert_not_called()


def test_handle_resume_session_halts_on_preflight_failure():
    # Arrange
    container = Container()
    mock_session_manager = MagicMock(spec=ISessionManager)
    mock_orchestrator = MagicMock(spec=IRunPlanUseCase)
    mock_llm_client = MagicMock(spec=ILlmClient)
    mock_config_service = MagicMock(spec=IConfigService)

    container.register(ISessionManager, instance=mock_session_manager)
    container.register(IRunPlanUseCase, instance=mock_orchestrator)
    container.register(ILlmClient, instance=mock_llm_client)
    container.register(IConfigService, instance=mock_config_service)

    mock_llm_client.validate_config.return_value = ["API Key is placeholder"]
    mock_config_service.get_config_path.return_value = ".teddy/config.yaml"

    # Act & Assert
    with pytest.raises(typer.Exit) as excinfo:
        handle_resume_session(container=container, path="my-session")

    assert excinfo.value.exit_code == 1
    # Assert: Orchestrator was NEVER called
    mock_orchestrator.resume.assert_not_called()


def test_handle_plan_generation_halts_on_preflight_failure():
    # Arrange
    container = Container()
    mock_planning_service = MagicMock(spec=IPlanningUseCase)
    mock_llm_client = MagicMock(spec=ILlmClient)
    mock_config_service = MagicMock(spec=IConfigService)

    container.register(IPlanningUseCase, instance=mock_planning_service)
    container.register(ILlmClient, instance=mock_llm_client)
    container.register(IConfigService, instance=mock_config_service)

    mock_llm_client.validate_config.return_value = ["API Key is placeholder"]
    mock_config_service.get_config_path.return_value = ".teddy/config.yaml"

    # Act & Assert
    with pytest.raises(typer.Exit) as excinfo:
        handle_plan_generation(container=container, message="Generate a test")

    assert excinfo.value.exit_code == 1
    # Assert: Planning service was NEVER called
    mock_planning_service.generate_plan.assert_not_called()
