"""
Regression test: Resume should update meta.yaml with model/provider/api_key overrides.
"""

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

            # save_meta should still be called, but model should remain unchanged
            if repo.save_meta.called:
                call_args = repo.save_meta.call_args
                saved_data = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
                assert saved_data.get("model") == "preserved-model", (
                    f"Expected model 'preserved-model' but got {saved_data.get('model')}"
                )
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
            assert saved_data.get("model") == "some-model"
        finally:
            handlers._orchestrate_session_loop = original_loop
