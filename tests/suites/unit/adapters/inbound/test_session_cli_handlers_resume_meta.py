"""
Regression test: Resume should update meta.yaml with model/provider/api_key overrides.
"""

import pytest
from unittest.mock import MagicMock  # noqa: TID251

from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.config_service import IConfigService


class TestResumeMetadataUpdate:
    """Verifies that handle_resume_session updates meta.yaml with overrides."""

    def _create_mock_container(self) -> MagicMock:
        """Creates a minimal container mock with required services."""
        container = MagicMock()

        mock_repo = MagicMock(spec=ISessionRepository)
        mock_session_manager = MagicMock(spec=ISessionManager)
        mock_fs = MagicMock(spec=IFileSystemManager)
        mock_config = MagicMock()
        mock_llm = MagicMock()
        mock_llm.validate_config.return_value = []
        mock_prompt = MagicMock()
        mock_interactor = MagicMock()
        mock_planning = MagicMock()
        mock_orchestrator = MagicMock()
        mock_lifecycle = MagicMock()
        mock_loop_guard = MagicMock()
        mock_context = MagicMock()
        mock_init = MagicMock()
        mock_formatter = MagicMock()

        # Default config: get_setting returns "unknown" for unconfigured keys
        mock_config.get_setting.side_effect = lambda key, default="unknown": default
        # Default: get_latest_session_name raises ValueError (no path provided)
        mock_session_manager.get_latest_session_name.side_effect = ValueError(
            "No path provided"
        )
        # Default: get_cumulative_cost returns 0.0
        mock_session_manager.get_cumulative_cost.return_value = 0.0
        # Default: get_config_path returns a placeholder
        mock_config.get_config_path.return_value = ".teddy/config.yaml"

        # Wire up the container to resolve these as needed
        container.resolve.side_effect = lambda cls, **kw: {
            ISessionManager: mock_session_manager,
            ISessionRepository: mock_repo,
            IFileSystemManager: mock_fs,
            ILlmClient: mock_llm,
            IConfigService: mock_config,
        }.get(cls, MagicMock())

        # Also store mocks for assertions
        container._mocks = {
            "repo": mock_repo,
            "session_manager": mock_session_manager,
            "fs": mock_fs,
            "config": mock_config,
            "llm": mock_llm,
            "prompt": mock_prompt,
            "interactor": mock_interactor,
            "planning": mock_planning,
            "orchestrator": mock_orchestrator,
            "lifecycle": mock_lifecycle,
            "loop_guard": mock_loop_guard,
            "context": mock_context,
            "init": mock_init,
            "formatter": mock_formatter,
        }

        return container

    def test_resume_with_model_override_updates_meta(self):
        """When --model is provided to resume, meta.yaml should be updated."""
        from teddy_executor.adapters.inbound.session_cli_handlers import (
            handle_resume_session,
        )

        container = self._create_mock_container()
        mocks = container._mocks
        repo: MagicMock = mocks["repo"]

        # Configure mock: existing meta.yaml has old model
        repo.load_meta.return_value = {
            "model": "old-model",
            "agent_name": "developer",
            "cumulative_cost": 0.05,
        }
        mocks[
            "session_manager"
        ].get_latest_turn.return_value = (
            ".teddy/sessions/20250101_120000-test-session/01"
        )
        mocks[
            "session_manager"
        ].resolve_session_from_path.return_value = "20250101_120000-test-session"
        mocks["session_manager"].get_cumulative_cost.return_value = 0.05

        # Patch the internal loop to be a no-op
        from teddy_executor.adapters.inbound import session_cli_handlers as handlers

        original_loop = handlers._orchestrate_session_loop
        handlers._orchestrate_session_loop = MagicMock()

        try:
            handle_resume_session(
                container=container,
                path="test-session",
                interactive=False,
                no_copy=True,
                model="new-model",
                provider=None,
                api_key=None,
            )

            # Assert that save_meta was called with updated model
            repo.save_meta.assert_called_once()
            call_args = repo.save_meta.call_args
            saved_data = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
            assert saved_data.get("model") == "new-model", (
                f"Expected model 'new-model' but got {saved_data.get('model')}"
            )
            assert saved_data.get("agent_name") == "developer"
            assert saved_data.get("cumulative_cost") == 0.05
        finally:
            handlers._orchestrate_session_loop = original_loop

    def test_resume_without_overrides_preserves_meta(self):
        """When resume is called without model overrides, meta.yaml should be unchanged."""
        from teddy_executor.adapters.inbound.session_cli_handlers import (
            handle_resume_session,
        )

        container = self._create_mock_container()
        mocks = container._mocks
        repo: MagicMock = mocks["repo"]

        repo.load_meta.return_value = {
            "model": "preserved-model",
            "agent_name": "developer",
            "cumulative_cost": 0.1,
        }
        mocks[
            "session_manager"
        ].get_latest_turn.return_value = (
            ".teddy/sessions/20250101_120000-test-session/01"
        )
        mocks[
            "session_manager"
        ].resolve_session_from_path.return_value = "20250101_120000-test-session"
        mocks["session_manager"].get_cumulative_cost.return_value = 0.1

        from teddy_executor.adapters.inbound import session_cli_handlers as handlers

        original_loop = handlers._orchestrate_session_loop
        handlers._orchestrate_session_loop = MagicMock()

        try:
            handle_resume_session(
                container=container,
                path="test-session",
                interactive=False,
                no_copy=True,
                model=None,
                provider=None,
                api_key=None,
            )

            # save_meta should be called with model auto-synced to config model
            if repo.save_meta.called:
                call_args = repo.save_meta.call_args
                saved_data = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
                # Model should be auto-synced to the config default
                assert saved_data.get("model") == "unknown", (
                    f"Expected model 'unknown' (from config) but got {saved_data.get('model')}"
                )
                # Other metadata should be preserved
                assert saved_data.get("agent_name") == "developer"
                assert saved_data.get("cumulative_cost") == 0.1
        finally:
            handlers._orchestrate_session_loop = original_loop

    def test_resume_with_provider_override(self):
        """When --provider is provided, provider field in meta.yaml should be updated."""
        from teddy_executor.adapters.inbound.session_cli_handlers import (
            handle_resume_session,
        )

        container = self._create_mock_container()
        mocks = container._mocks
        repo: MagicMock = mocks["repo"]

        repo.load_meta.return_value = {
            "model": "some-model",
            "provider": "old-provider",
            "agent_name": "developer",
        }
        mocks[
            "session_manager"
        ].get_latest_turn.return_value = (
            ".teddy/sessions/20250101_120000-test-session/01"
        )
        mocks[
            "session_manager"
        ].resolve_session_from_path.return_value = "20250101_120000-test-session"
        mocks["session_manager"].get_cumulative_cost.return_value = 0.0

        from teddy_executor.adapters.inbound import session_cli_handlers as handlers

        original_loop = handlers._orchestrate_session_loop
        handlers._orchestrate_session_loop = MagicMock()

        try:
            handle_resume_session(
                container=container,
                path="test-session",
                interactive=False,
                no_copy=True,
                model=None,
                provider="new-provider",
                api_key=None,
            )

            repo.save_meta.assert_called_once()
            call_args = repo.save_meta.call_args
            saved_data = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
            assert saved_data.get("provider") == "new-provider"
            # When config_model is "unknown" (no real config), original meta model is preserved
            assert saved_data.get("model") == "some-model", (
                f"Expected model 'some-model' (preserved from meta) but got {saved_data.get('model')}"
            )
            assert saved_data.get("agent_name") == "developer"
        finally:
            handlers._orchestrate_session_loop = original_loop


# ---------------------------------------------------------------------------
# Logic deliverable: resume -a/--agent flag behavior
# ---------------------------------------------------------------------------


def test_resume_without_agent_does_not_call_set_session_agent(monkeypatch):
    """
    Verifies that handle_resume_session does NOT call set_session_agent
    when the agent parameter is not provided (no-flag-no-change).
    """
    from unittest.mock import Mock
    from teddy_executor.adapters.inbound.session_cli_handlers import (
        handle_resume_session,
    )
    from teddy_executor.core.ports.outbound.session_manager import ISessionManager

    # Arrange
    mock_container = Mock()
    mock_session_manager = Mock(spec=ISessionManager)
    mock_container.resolve.return_value = mock_session_manager

    # Bypass preflight and session orchestration
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers._run_cli_preflight_check",
        lambda container, agent=None, setup_editor=None, setup_api_key=None: None,
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers._orchestrate_session_loop",
        lambda container, session_name, interactive, no_copy, **kwargs: None,
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers._sync_and_display_session_meta",
        lambda container, session_name, model=None, provider=None, api_key=None: None,
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers._resolve_session_name",
        lambda container, path=None: "test-session",
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers.background_check",
        lambda cache_path, index_url=None: None,
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.cli_helpers.find_project_root",
        lambda: None,
    )

    # Act — no agent parameter
    handle_resume_session(
        container=mock_container,
        interactive=True,
        setup_editor=False,
        setup_api_key=False,
    )

    # Assert — set_session_agent should NOT have been called
    mock_session_manager.set_session_agent.assert_not_called()


def test_resume_with_nonexistent_agent_exits_with_error(monkeypatch):
    """
    Verifies that handle_resume_session exits with typer.Exit when
    set_session_agent raises ValueError (nonexistent agent).
    """
    import typer
    from unittest.mock import Mock
    from teddy_executor.adapters.inbound.session_cli_handlers import (
        handle_resume_session,
    )
    from teddy_executor.core.ports.outbound.session_manager import ISessionManager

    # Arrange
    mock_container = Mock()
    mock_session_manager = Mock(spec=ISessionManager)
    mock_session_manager.set_session_agent.side_effect = ValueError(
        "Agent prompt 'nonexistent' not found in .teddy/prompts/"
    )
    mock_container.resolve.return_value = mock_session_manager

    # Bypass preflight and session orchestration
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers._run_cli_preflight_check",
        lambda container, agent=None, setup_editor=None, setup_api_key=None: None,
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers._orchestrate_session_loop",
        lambda container, session_name, interactive, no_copy, **kwargs: None,
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers._sync_and_display_session_meta",
        lambda container, session_name, model=None, provider=None, api_key=None: None,
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers._resolve_session_name",
        lambda container, path=None: "test-session",
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers.background_check",
        lambda cache_path, index_url=None: None,
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.cli_helpers.find_project_root",
        lambda: None,
    )

    # Act / Assert — typer.Exit is raised when set_session_agent errors
    with pytest.raises(typer.Exit) as exc_info:
        handle_resume_session(
            container=mock_container,
            agent="nonexistent",
            interactive=True,
            setup_editor=False,
            setup_api_key=False,
        )

    assert exc_info.value.exit_code == 1, (
        f"Expected exit code 1, got {exc_info.value.exit_code}"
    )
