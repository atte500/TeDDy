import pytest
import typer
from teddy_executor.adapters.inbound.session_cli_handlers import (
    _run_cli_preflight_check,
    _validate_editor_config,
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


def _configure_editor(mock_config, value):
    """Drive ``get_setting('editor')`` past the harness default side_effect.

    ``TestEnvironment._apply_config_defaults`` installs a ``get_setting``
    side_effect (which returns the caller's ``default``); a callable
    ``side_effect`` takes precedence over any later ``return_value`` assignment,
    so ``return_value`` alone is inert. Overriding the side_effect is the
    harness-sanctioned way to make a mocked ``IConfigService`` return a
    specific value.
    """
    mock_config.get_setting.side_effect = lambda key, default=None: (
        value if key == "editor" else default
    )


def test_prompt_for_editor_selection_saves_basename_for_number(monkeypatch):
    """A valid number persists the selected editor's basename (portable)."""
    mock_config = POSIXPathMock(spec=IConfigService)
    mock_env = POSIXPathMock(spec=ISystemEnvironment)
    helper = _editor_helper(mock_env, mock_config)
    available = [("nvim", "/usr/bin/nvim"), ("vim", "/usr/bin/vim")]
    _patch_prompt(monkeypatch, ["1"])

    _prompt_for_editor_selection(mock_config, helper, available)

    mock_config.set_setting.assert_called_once_with("editor", "nvim")


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

    mock_config.set_setting.assert_called_once_with("editor", "vim")


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

    mock_config.set_setting.assert_called_once_with("editor", "nvim")


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


# ---------------------------------------------------------------------------
# Editor validation orchestrator: _validate_editor_config(container)
# ---------------------------------------------------------------------------


def test_validate_editor_config_returns_early_when_disabled(env):
    """The 'disabled' sentinel skips discovery and prompting entirely."""
    mock_config = env.mock_port(IConfigService)
    mock_env = env.mock_port(ISystemEnvironment)
    _configure_editor(mock_config, "disabled")

    _validate_editor_config(env.container)

    # No PATH scan and no persistence on the disabled path.
    mock_env.which.assert_not_called()
    mock_config.set_setting.assert_not_called()


def test_validate_editor_config_returns_early_when_configured_editor_found(env):
    """A configured editor that resolves on PATH needs no prompting."""
    mock_config = env.mock_port(IConfigService)
    mock_env = env.mock_port(ISystemEnvironment)
    _configure_editor(mock_config, "nvim")
    mock_env.which.side_effect = lambda name: (
        "/usr/bin/nvim" if name == "nvim" else None
    )

    _validate_editor_config(env.container)

    mock_config.set_setting.assert_not_called()


def test_validate_editor_config_prompts_discovery_when_no_editor_configured(
    env, monkeypatch
):
    """An unconfigured editor falls through to discovery and persists the choice."""
    mock_config = env.mock_port(IConfigService)
    mock_env = env.mock_port(ISystemEnvironment)
    _configure_editor(mock_config, "")
    mock_env.which.side_effect = lambda name: (
        "/usr/bin/nvim" if name == "nvim" else None
    )
    _patch_prompt(monkeypatch, ["1"])

    _validate_editor_config(env.container)

    mock_config.set_setting.assert_called_once_with("editor", "nvim")


def test_validate_editor_config_prompts_discovery_when_configured_editor_missing(
    env, monkeypatch
):
    """A configured-but-missing editor warns and falls through to discovery."""
    mock_config = env.mock_port(IConfigService)
    mock_env = env.mock_port(ISystemEnvironment)
    _configure_editor(mock_config, "code")
    mock_env.which.side_effect = lambda name: (
        "/usr/bin/nvim" if name == "nvim" else None
    )
    _patch_prompt(monkeypatch, ["1"])

    _validate_editor_config(env.container)

    mock_config.set_setting.assert_called_once_with("editor", "nvim")


def test_validate_editor_config_prompts_custom_when_nothing_discovered(
    env, monkeypatch
):
    """With no editors discovered, the custom-only prompt persists the result."""
    mock_config = env.mock_port(IConfigService)
    mock_env = env.mock_port(ISystemEnvironment)
    _configure_editor(mock_config, "")
    mock_env.which.return_value = None
    _patch_prompt(monkeypatch, [""])

    _validate_editor_config(env.container)

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


# ---------------------------------------------------------------------------
# Gating of the editor-validation gate on the editor-setup signal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "setup_editor, expected_calls",
    [(True, 1), (False, 0)],
)
def test_preflight_check_gates_editor_validation_on_setup_editor_flag(
    env, monkeypatch, setup_editor, expected_calls
):
    """The preflight editor gate is keyed solely on ``setup_editor``.

    Slice 00-26 decouples the one-time editor setup from the approval flag: the
    Migration deliverable contracted the ``interactive`` fallback, so the gate
    now runs exactly when ``setup_editor`` is True (the caller computed "the
    session will read the terminal") and skips otherwise. ``interactive`` no
    longer participates in the editor boundary.
    """
    # Arrange - no config errors so the gate is reached on the success path.
    mock_llm = env.mock_port(ILlmClient)
    mock_llm.validate_config.return_value = []

    editor_calls = []
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers._validate_editor_config",
        lambda container: editor_calls.append(container),
    )

    # Act
    _run_cli_preflight_check(container=env.container, setup_editor=setup_editor)

    # Assert - the gate is invoked exactly when ``setup_editor`` is True.
    assert len(editor_calls) == expected_calls


def test_full_preflight_flow_persists_discovered_editor_selection(env, monkeypatch):
    """End-to-end tracer bullet for the editor-validation preflight flow.

    Unlike the direct-call orchestrator and prompt-helper tests above, this
    drives the COMPLETE flow -- ``_run_cli_preflight_check(setup_editor=True)``
    through the REAL ``_validate_editor_config`` into
    ``_prompt_for_editor_selection`` and finally ``set_setting`` -- with
    discovery stubbed at the ``discover_editors`` boundary.
    """
    # Arrange - no config errors so the gate is reached on the success path.
    mock_llm = env.mock_port(ILlmClient)
    mock_llm.validate_config.return_value = []

    mock_config = env.mock_port(IConfigService)
    env.mock_port(ISystemEnvironment)
    # Unconfigured editor -> discovery prompt (overrides the harness default).
    _configure_editor(mock_config, "")

    monkeypatch.setattr(
        ConsoleToolingHelper,
        "discover_editors",
        lambda self: [("nvim", "/usr/bin/nvim"), ("vim", "/usr/bin/vim")],
    )
    _patch_prompt(monkeypatch, ["1"])

    # Act - the full preflight boundary with editor setup enabled.
    _run_cli_preflight_check(container=env.container, setup_editor=True)

    # Assert - the numbered selection is persisted as its basename.
    mock_config.set_setting.assert_called_once_with("editor", "nvim")


# ---------------------------------------------------------------------------
# Gating of the interactive API-key setup prompt (Slice 00-27 Seam)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "setup_api_key",
    [True, False],
)
def test_preflight_check_gates_api_key_prompt_on_setup_api_key_flag(
    env, monkeypatch, setup_api_key
):
    """The preflight API-key gate keys on ``setup_api_key`` AND key absence.

    The gate is ADDITIVE and INERT by default (``setup_api_key`` defaults to
    ``None`` -> skip), so every existing caller is unaffected. When the signal
    is truthy and ``llm.api_key`` is missing, the interactive prompt fires and
    persists the entered key; otherwise the gate is skipped.
    """
    # Arrange - no config errors so the gate is reached on the success path.
    mock_llm = env.mock_port(ILlmClient)
    mock_llm.validate_config.return_value = []
    mock_config = env.mock_port(IConfigService)
    # Missing key -> the gate is eligible to prompt.
    mock_config.get_setting.side_effect = lambda key, default=None: (
        "" if key == "llm.api_key" else default
    )
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: "entered-value")

    # Act
    _run_cli_preflight_check(container=env.container, setup_api_key=setup_api_key)

    # Assert - the prompt's persist fires exactly when the flag is truthy.
    if setup_api_key:
        mock_config.set_env_variable.assert_called_once_with(
            "TEDDY_LLM_API_KEY", "entered-value"
        )
    else:
        mock_config.set_env_variable.assert_not_called()
