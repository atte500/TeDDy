import pytest
import typer
from teddy_executor.adapters.inbound.session_cli_handlers import (
    _run_cli_preflight_check,
    _prompt_for_editor_selection,
    _prompt_for_custom_editor,
    handle_new_session,
    handle_resume_session,
    handle_plan_generation,
)
from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from tests.harness.setup.mocking import POSIXPathMock
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.domain.models.exceptions import ConfigurationError


# ---------------------------------------------------------------------------
# Editor validation flow: console prompting helpers (Slice 03-01)
# ---------------------------------------------------------------------------


def _patch_prompt(monkeypatch, values):
    """Feed the given strings to successive ``typer.prompt`` calls."""
    iterator = iter(values)
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: next(iterator))


def _editor_helper(mock_env, mock_config):
    """Build a real ConsoleToolingHelper over auto-specced env/config doubles."""
    return ConsoleToolingHelper(mock_env, mock_config)


def test_prompt_for_editor_selection_saves_resolved_path_for_number(monkeypatch):
    """A valid number persists the selected editor's resolved absolute path."""
    mock_config = POSIXPathMock(spec=IConfigService)
    mock_env = POSIXPathMock(spec=ISystemEnvironment)
    helper = _editor_helper(mock_env, mock_config)
    available = [("nvim", "/usr/bin/nvim"), ("vim", "/usr/bin/vim")]
    _patch_prompt(monkeypatch, ["1"])

    _prompt_for_editor_selection(mock_config, helper, available)

    mock_config.set_setting.assert_called_once_with("editor", "/usr/bin/nvim")


def test_prompt_for_editor_selection_saves_custom_command_as_typed(monkeypatch):
    """An available custom command is persisted exactly as typed (flags kept)."""
    mock_config = POSIXPathMock(spec=IConfigService)
    mock_env = POSIXPathMock(spec=ISystemEnvironment)
    mock_env.which.side_effect = lambda name: (
        "/usr/bin/code" if name == "code" else None
    )
    helper = _editor_helper(mock_env, mock_config)
    available = [("nvim", "/usr/bin/nvim")]
    _patch_prompt(monkeypatch, ["code --wait"])

    _prompt_for_editor_selection(mock_config, helper, available)

    mock_config.set_setting.assert_called_once_with("editor", "code --wait")


def test_prompt_for_editor_selection_saves_disabled_on_empty_input(monkeypatch):
    """Empty input persists the 'disabled' sentinel."""
    mock_config = POSIXPathMock(spec=IConfigService)
    mock_env = POSIXPathMock(spec=ISystemEnvironment)
    helper = _editor_helper(mock_env, mock_config)
    available = [("nvim", "/usr/bin/nvim")]
    _patch_prompt(monkeypatch, [""])

    _prompt_for_editor_selection(mock_config, helper, available)

    mock_config.set_setting.assert_called_once_with("editor", "disabled")


def test_prompt_for_editor_selection_reprompts_on_invalid_number(monkeypatch):
    """An out-of-range number re-prompts until a valid number is given."""
    mock_config = POSIXPathMock(spec=IConfigService)
    mock_env = POSIXPathMock(spec=ISystemEnvironment)
    helper = _editor_helper(mock_env, mock_config)
    available = [("nvim", "/usr/bin/nvim"), ("vim", "/usr/bin/vim")]
    _patch_prompt(monkeypatch, ["9", "2"])

    _prompt_for_editor_selection(mock_config, helper, available)

    mock_config.set_setting.assert_called_once_with("editor", "/usr/bin/vim")


def test_prompt_for_editor_selection_reprompts_on_unavailable_custom(monkeypatch):
    """An unavailable custom command re-prompts (never accepted without which())."""
    mock_config = POSIXPathMock(spec=IConfigService)
    mock_env = POSIXPathMock(spec=ISystemEnvironment)
    mock_env.which.side_effect = lambda name: (
        "/usr/bin/nvim" if name == "nvim" else None
    )
    helper = _editor_helper(mock_env, mock_config)
    available = [("nvim", "/usr/bin/nvim")]
    _patch_prompt(monkeypatch, ["bogus", "1"])

    _prompt_for_editor_selection(mock_config, helper, available)

    mock_config.set_setting.assert_called_once_with("editor", "/usr/bin/nvim")


def test_prompt_for_custom_editor_saves_command_as_typed(monkeypatch):
    """The custom-only branch persists an available command as typed."""
    mock_config = POSIXPathMock(spec=IConfigService)
    mock_env = POSIXPathMock(spec=ISystemEnvironment)
    mock_env.which.side_effect = lambda name: (
        "/opt/bin/myeditor" if name == "myeditor" else None
    )
    helper = _editor_helper(mock_env, mock_config)
    _patch_prompt(monkeypatch, ["myeditor"])

    _prompt_for_custom_editor(mock_config, helper)

    mock_config.set_setting.assert_called_once_with("editor", "myeditor")


def test_prompt_for_custom_editor_saves_disabled_on_empty_input(monkeypatch):
    """The custom-only branch persists 'disabled' on empty input."""
    mock_config = POSIXPathMock(spec=IConfigService)
    mock_env = POSIXPathMock(spec=ISystemEnvironment)
    helper = _editor_helper(mock_env, mock_config)
    _patch_prompt(monkeypatch, [""])

    _prompt_for_custom_editor(mock_config, helper)

    mock_config.set_setting.assert_called_once_with("editor", "disabled")


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
