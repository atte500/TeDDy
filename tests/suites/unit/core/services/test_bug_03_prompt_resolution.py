"""Regression tests for Bug #03: Case-insensitive prompt resolution and duplicate Initial Request."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from teddy_executor.core.services.prompt_manager import PromptManager
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
)


class TestPromptCaseSensitivity:
    """Verifies that _find_prompt_file resolves case-insensitively."""

    def test_fetch_system_prompt_ignores_case(self, mock_fs, mock_user_interactor):
        """fetch_system_prompt with 'Pathfinder' must find 'pathfinder.xml'."""
        prompt_manager = PromptManager(
            file_system_manager=mock_fs, user_interactor=mock_user_interactor
        )
        turn_path = Path(".teddy/sessions/my-session/01")
        agent_name = "Pathfinder"

        session_root = turn_path.parent.as_posix()
        teddy_prompts_dir = (
            turn_path.parent.parent.parent.parent / ".teddy" / "prompts"
        ).as_posix()

        # Mock: no session-root prompt, .teddy/prompts/ has pathfinder.xml
        mock_fs.list_directory.side_effect = lambda d: {
            teddy_prompts_dir: ["pathfinder.xml"],
            session_root: [],
        }.get(d, [])
        mock_fs.path_exists.side_effect = lambda path: (
            path
            in [
                teddy_prompts_dir,
                f"{teddy_prompts_dir}/pathfinder.xml",
            ]
        )
        mock_fs.read_file.side_effect = lambda p: {
            f"{teddy_prompts_dir}/pathfinder.xml": "You are a pathfinder agent.",
        }.get(p, "")

        result = prompt_manager.fetch_system_prompt(agent_name, turn_path)
        assert result == "You are a pathfinder agent."


class TestLifecycleNoDuplicateInitialRequest:
    """Verifies that the lifecycle manager does NOT print the initial request."""

    def test_lifecycle_manager_does_not_print_initial_request(self):
        """When resuming first turn, lifecycle manager must not call _print_initial_request."""
        # Arrange: mock _print_initial_request on the session_orchestrator module
        with patch(
            "teddy_executor.core.services.session_orchestrator._print_initial_request"
        ) as mock_print:
            # Build minimal mock ports object
            ports = MagicMock()
            ports.session_service = MagicMock()
            ports.session_service.get_session_state.return_value = (
                "EMPTY",  # SessionState.EMPTY
                ".teddy/sessions/test/01",
            )
            ports.session_service.transition_to_next_turn.return_value = (
                ".teddy/sessions/test/02"
            )
            ports.file_system_manager = MagicMock()
            ports.report_formatter = MagicMock()
            ports.user_interactor = MagicMock()
            ports.session_planner = MagicMock()
            ports.session_planner.trigger_new_plan.return_value = "test"
            ports.replanner = MagicMock()

            lifecycle = SessionLifecycleManager(ports)

            # Act: simulate resume for EMPTY state
            mock_orchestrator = MagicMock()
            mock_orchestrator.execute.return_value = MagicMock(run_summary=MagicMock())
            lifecycle.resume(
                "test",
                mock_orchestrator,
                interactive=False,
            )

            # Assert: _print_initial_request should NOT have been called
            # (The orchestrator will do it later)
            mock_print.assert_not_called()
