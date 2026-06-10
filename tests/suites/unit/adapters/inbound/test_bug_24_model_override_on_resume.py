"""
Regression test: Resume should clear actual_model from meta.yaml.
"""

from unittest.mock import MagicMock  # noqa: TID251

from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.config_service import IConfigService


class TestResumeClearsActualModel:
    """Verifies that handle_resume_session clears actual_model from meta.yaml."""

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

    def test_resume_clears_actual_model_from_meta(self):
        """
        When resume is called with a model override, actual_model should be
        cleared from the saved meta.yaml so that the display falls through
        to the current model.
        """
        from teddy_executor.adapters.inbound.session_cli_handlers import (
            handle_resume_session,
        )

        container = self._create_mock_container()
        mocks = container._mocks
        repo: MagicMock = mocks["repo"]

        # Configure mock: existing meta.yaml has actual_model (stale from previous turn)
        repo.load_meta.return_value = {
            "model": "old-model",
            "actual_model": "stale-serving-model",
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

            # Assert that save_meta was called and actual_model is NOT in saved data
            repo.save_meta.assert_called_once()
            call_args = repo.save_meta.call_args
            # save_meta path is first positional arg, data is second
            saved_data = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
            # actual_model should be absent (cleared on resume)
            assert "actual_model" not in saved_data, (
                f"actual_model should be cleared on resume, but found: {saved_data.get('actual_model')}"
            )
            # model override should still be present
            assert saved_data.get("model") == "new-model", (
                f"Expected model 'new-model' but got {saved_data.get('model')}"
            )
        finally:
            handlers._orchestrate_session_loop = original_loop

    def test_resume_clears_actual_model_without_override(self):
        """
        Even without a model override, actual_model should be cleared
        so the display falls through to the default/config model.
        """
        from teddy_executor.adapters.inbound.session_cli_handlers import (
            handle_resume_session,
        )

        container = self._create_mock_container()
        mocks = container._mocks
        repo: MagicMock = mocks["repo"]

        repo.load_meta.return_value = {
            "model": "old-model",
            "actual_model": "stale-serving-model",
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

            # save_meta should be called (auto-sync to config model)
            if repo.save_meta.called:
                call_args = repo.save_meta.call_args
                saved_data = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
                # actual_model should be absent
                assert "actual_model" not in saved_data, (
                    f"actual_model should be cleared on resume, but found: {saved_data.get('actual_model')}"
                )
        finally:
            handlers._orchestrate_session_loop = original_loop
