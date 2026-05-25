import pytest
import typer
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


def test_handle_new_session_halts_on_preflight_failure_before_prompt(env):
    # Arrange
    mock_session_manager = env.mock_port(ISessionManager)
    mock_user_interactor = env.mock_port(IUserInteractor)
    mock_llm_client = env.mock_port(ILlmClient)
    mock_config_service = env.mock_port(IConfigService)

    # Set up preflight failure
    mock_llm_client.validate_config.return_value = ["API Key is placeholder"]
    mock_config_service.get_config_path.return_value = ".teddy/config.yaml"

    # Act & Assert
    # We expect a typer.Exit(1) due to the error handling in the handler
    with pytest.raises(typer.Exit) as excinfo:
        handle_new_session(
            container=env.container,
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
    # Assert: Only local validation was performed
    mock_llm_client.validate_config.assert_called_once_with(include_remote=False)


def test_handle_resume_session_halts_on_preflight_failure(env):
    # Arrange
    env.mock_port(ISessionManager)
    mock_orchestrator = env.mock_port(IRunPlanUseCase)
    mock_llm_client = env.mock_port(ILlmClient)
    mock_config_service = env.mock_port(IConfigService)

    mock_llm_client.validate_config.return_value = ["API Key is placeholder"]
    mock_config_service.get_config_path.return_value = ".teddy/config.yaml"

    # Act & Assert
    with pytest.raises(typer.Exit) as excinfo:
        handle_resume_session(container=env.container, path="my-session")

    assert excinfo.value.exit_code == 1
    # Assert: Orchestrator was NEVER called
    mock_orchestrator.resume.assert_not_called()
    # Assert: Only local validation was performed
    mock_llm_client.validate_config.assert_called_once_with(include_remote=False)


def test_handle_plan_generation_halts_on_preflight_failure(env):
    # Arrange
    mock_planning_service = env.mock_port(IPlanningUseCase)
    mock_llm_client = env.mock_port(ILlmClient)
    mock_config_service = env.mock_port(IConfigService)

    mock_llm_client.validate_config.return_value = ["API Key is placeholder"]
    mock_config_service.get_config_path.return_value = ".teddy/config.yaml"

    # Act & Assert
    with pytest.raises(typer.Exit) as excinfo:
        handle_plan_generation(container=env.container, message="Generate a test")

    assert excinfo.value.exit_code == 1
    # Assert: Planning service was NEVER called
    mock_planning_service.generate_plan.assert_not_called()
    # Assert: Only local validation was performed
    mock_llm_client.validate_config.assert_called_once_with(include_remote=False)
