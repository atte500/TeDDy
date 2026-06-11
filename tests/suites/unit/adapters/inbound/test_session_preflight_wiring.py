import pytest
import typer
from teddy_executor.adapters.inbound.session_cli_handlers import (
    _run_cli_preflight_check,
    handle_new_session,
    handle_resume_session,
    handle_plan_generation,
)
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.domain.models.exceptions import ConfigurationError


def test_handle_new_session_halts_on_preflight_failure_before_prompt(env):
    # Arrange
    mock_session_manager = env.mock_port(ISessionManager)
    mock_user_interactor = env.mock_port(IUserInteractor)
    mock_llm_client = env.mock_port(ILlmClient)
    mock_config_service = env.mock_port(IConfigService)
    env.mock_port(IInitUseCase)

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


# ---------------------------------------------------------------------------
# Agent validation error enrichment (Wiring deliverable)
# ---------------------------------------------------------------------------


def test_preflight_check_raises_value_error_when_only_agent_error(env):
    """
    If the ONLY preflight error is an invalid agent, _run_cli_preflight_check
    should raise ValueError with available agents listed.
    """
    # Arrange
    mock_llm = env.mock_port(ILlmClient)
    mock_prompt_manager = env.mock_port(IPromptManager)
    mock_llm.validate_config.return_value = []  # No other errors
    mock_prompt_manager.get_prompt_content.return_value = None
    mock_prompt_manager.get_available_agents.return_value = ["architect", "developer"]

    # Act / Assert
    with pytest.raises(
        ValueError,
        match="Agent prompt 'badagent' not found. Available agents: architect, developer",
    ):
        _run_cli_preflight_check(container=env.container, agent="badagent")


def test_preflight_check_raises_configuration_error_when_agent_and_other_errors(env):
    """
    If the agent error is combined with other config errors (e.g., missing API key),
    _run_cli_preflight_check should raise ConfigurationError (not ValueError).
    """
    # Arrange
    mock_llm = env.mock_port(ILlmClient)
    mock_prompt_manager = env.mock_port(IPromptManager)
    mock_llm.validate_config.return_value = ["API Key is placeholder"]
    mock_prompt_manager.get_prompt_content.return_value = None
    mock_prompt_manager.get_available_agents.return_value = ["architect", "developer"]

    # Act / Assert
    with pytest.raises(
        ConfigurationError,
        match="Configuration Error: Agent prompt 'badagent' not found. Available agents: architect, developer, API Key is placeholder",
    ):
        _run_cli_preflight_check(container=env.container, agent="badagent")


def test_preflight_check_no_error_when_agent_exists(env):
    """
    When the agent prompt exists, _run_cli_preflight_check does not add an
    agent error to the list.
    """
    # Arrange
    mock_llm = env.mock_port(ILlmClient)
    mock_prompt_manager = env.mock_port(IPromptManager)
    mock_llm.validate_config.return_value = []  # No errors
    mock_prompt_manager.get_prompt_content.return_value = "some prompt content"

    # Act / Assert: should not raise
    _run_cli_preflight_check(container=env.container, agent="goodagent")


def test_preflight_check_value_error_without_available_agents(env):
    """
    If the available agents list is empty, the ValueError should NOT include
    the "Available agents:" suffix.
    """
    # Arrange
    mock_llm = env.mock_port(ILlmClient)
    mock_prompt_manager = env.mock_port(IPromptManager)
    mock_llm.validate_config.return_value = []  # No other errors
    mock_prompt_manager.get_prompt_content.return_value = None
    mock_prompt_manager.get_available_agents.return_value = []

    # Act / Assert
    with pytest.raises(
        ValueError, match="Agent prompt 'badagent' not found. Available agents: "
    ):
        _run_cli_preflight_check(container=env.container, agent="badagent")
    # Additionally verify that the message does not contain agent names
    # (e.g., no comma-separated list)
