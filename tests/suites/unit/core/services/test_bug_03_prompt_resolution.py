"""Regression tests for Bug #03: Case-insensitive prompt resolution and duplicate Initial Request."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.session_manager import SessionState
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


class TestLifecyclePrintsInitialRequest:
    """Verifies that the lifecycle manager prints the initial request."""

    def test_lifecycle_manager_prints_initial_request(self):
        """When resuming first turn, lifecycle manager must call _print_initial_request."""
        # Arrange: mock _print_initial_request on the session_orchestrator module
        with patch(
            "teddy_executor.core.services.session_orchestrator._print_initial_request"
        ) as mock_print:
            # Build minimal mock ports object
            ports = MagicMock()
            ports.session_service = MagicMock()
            ports.session_service.get_session_state.return_value = (
                SessionState.EMPTY,
                ".teddy/sessions/test/01",
            )
            ports.session_service.transition_to_next_turn.return_value = (
                ".teddy/sessions/test/02",
            )
            ports.file_system_manager = MagicMock()
            ports.report_formatter = MagicMock()
            ports.user_interactor = MagicMock()
            ports.session_planner = MagicMock()
            ports.session_planner.trigger_new_plan.return_value = "test"
            ports.replanner = MagicMock()

            lifecycle = SessionLifecycleManager(ports)

            # Act: simulate resume for EMPTY state
            mock_orchestrator = MagicMock(spec=IRunPlanUseCase)
            mock_orchestrator.execute.return_value = MagicMock(run_summary=MagicMock())
            lifecycle.resume(
                "test",
                mock_orchestrator,
                interactive=False,
            )

            # Assert: _print_initial_request should have been called once
            mock_print.assert_called_once()
            call_args = mock_print.call_args
            assert call_args[0][0] is None, "message should be None"
            assert call_args[0][1] is True, "is_session should be True"

    def test_lifecycle_manager_does_not_print_initial_request_on_subsequent_turns(
        self,
    ):
        """When resuming a non-first turn, lifecycle manager must NOT call _print_initial_request."""
        with patch(
            "teddy_executor.core.services.session_orchestrator._print_initial_request"
        ) as mock_print:
            ports = MagicMock()
            ports.session_service = MagicMock()
            ports.session_service.get_session_state.return_value = (
                SessionState.COMPLETE_TURN,
                ".teddy/sessions/test/02",
            )
            ports.session_service.transition_to_next_turn.return_value = (
                ".teddy/sessions/test/03",
            )
            ports.file_system_manager = MagicMock()
            ports.report_formatter = MagicMock()
            ports.user_interactor = MagicMock()
            ports.session_planner = MagicMock()
            ports.session_planner.trigger_new_plan.return_value = "test"
            ports.replanner = MagicMock()

            lifecycle = SessionLifecycleManager(ports)

            mock_orchestrator = MagicMock(spec=IRunPlanUseCase)
            mock_orchestrator.execute.return_value = MagicMock(run_summary=MagicMock())
            lifecycle.resume(
                "test",
                mock_orchestrator,
                interactive=False,
            )

            # Assert: _print_initial_request should NOT have been called for turn 02+
            mock_print.assert_not_called()

    def test_print_initial_request_resolves_path_with_parent
        self, tmp_path, monkeypatch
    ):
        """_print_initial_request must resolve initial_request.md using Path(plan_path).parent
        (not .parent.parent) when plan_path is the turn directory."""
        from teddy_executor.core.services.session_orchestrator import (
            _print_initial_request,
        )

        # Create a temp session structure
        session_root = tmp_path / "my_session"
        session_root.mkdir()
        turn_dir = session_root / "01"
        turn_dir.mkdir()

        # Write initial_request.md at session root
        (session_root / "initial_request.md").write_text(
            "Hello from test\n", encoding="utf-8"
        )

        # Capture typer.secho calls
        calls = []
        monkeypatch.setattr(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            lambda text, **kwargs: calls.append(text),
        )

        # Act: call with plan_path = turn_dir (absolute, as the lifecycle manager does)
        _print_initial_request(
            message=None,
            is_session=True,
            plan_path=str(turn_dir),
        )

        # Assert: file content was found and printed
        assert len(calls) == 3, (
            f"Expected 3 calls (blank, label, content), got {len(calls)}: {calls}"
        )
        assert calls[0] == "", "First call should be blank line"
        assert calls[1] == "Initial Request:", "Second call should be the label"
        assert calls[2] == "Hello from test", (
            f"Third call should be the file content, got: {calls[2]}"
        )

    def test_print_initial_request_empty_file_no_output(self, tmp_path, monkeypatch):
        """_print_initial_request must produce no output when initial_request.md is empty."""
        from teddy_executor.core.services.session_orchestrator import (
            _print_initial_request,
        )

        session_root = tmp_path / "empty_session"
        session_root.mkdir()
        turn_dir = session_root / "01"
        turn_dir.mkdir()

        # Write empty file
        (session_root / "initial_request.md").write_text("", encoding="utf-8")

        calls = []
        monkeypatch.setattr(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            lambda text, **kwargs: calls.append(text),
        )

        _print_initial_request(
            message=None,
            is_session=True,
            plan_path=str(turn_dir),
        )

        assert len(calls) == 0, f"Expected no output for empty file, got: {calls}"

    def test_print_initial_request_no_file_no_output(self, tmp_path, monkeypatch):
        """_print_initial_request must produce no output when initial_request.md doesn't exist."""
        from teddy_executor.core.services.session_orchestrator import (
            _print_initial_request,
        )

        turn_dir = tmp_path / "no_session_file" / "01"
        turn_dir.mkdir(parents=True)

        calls = []
        monkeypatch.setattr(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            lambda text, **kwargs: calls.append(text),
        )

        _print_initial_request(
            message=None,
            is_session=True,
            plan_path=str(turn_dir),
        )

        assert len(calls) == 0, "Expected no output when file does not exist"
