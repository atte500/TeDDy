"""
Regression test for Bug #24: File content hash persists across turns, causing false
"File content modified during execution" failures when a file is externally modified.

Fix strategy: reset_file_hashes() is called at the start of each plan execution
(in ExecutionOrchestrator._process_plan_actions), clearing stale hashes from previous
turns. Within-plan detection is preserved because hashes are NOT reset between actions.
"""

from unittest.mock import create_autospec

from teddy_executor.core.domain.models import ActionData, ActionLog, ActionStatus
from teddy_executor.core.services.action_executor import ActionExecutor
from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator
from teddy_executor.core.ports.outbound import (
    IConfigService,
    IFileSystemManager,
    IUserInteractor,
)
from teddy_executor.core.services.action_dispatcher import ActionDispatcher


class TestHashStalenessCrossTurn:
    """Regression tests for Bug #24."""

    def _make_executor(
        self,
        file_system_manager: IFileSystemManager,
    ) -> tuple[ActionExecutor, ActionData]:
        """Creates an ActionExecutor and a sample EDIT action with mocked dispatcher."""
        action_dispatcher = create_autospec(ActionDispatcher)
        action_dispatcher.dispatch_and_execute.return_value = ActionLog(
            status=ActionStatus.SUCCESS,
            action_type="EDIT",
            params={"path": "/test/file.txt"},
            details="",
        )

        user_interactor = create_autospec(IUserInteractor)
        user_interactor.confirm_action.return_value = (True, "")

        edit_simulator = create_autospec(IEditSimulator)
        edit_simulator.simulate_edits.return_value = ("edited content", [])

        config_service = create_autospec(IConfigService)
        config_service.get_setting.return_value = 1.0

        file_system_manager.path_exists.return_value = True  # type: ignore[attr-defined]
        file_system_manager.read_file.return_value = ""  # type: ignore[attr-defined]
        file_system_manager.read_raw_file.return_value = ""  # type: ignore[attr-defined]

        executor = ActionExecutor(
            action_dispatcher=action_dispatcher,
            user_interactor=user_interactor,
            file_system_manager=file_system_manager,
            edit_simulator=edit_simulator,
            config_service=config_service,
        )

        action_params = {
            "path": "/test/file.txt",
            "FIND": "old line\n",
            "REPLACE": "new line\n",
        }
        action = ActionData(type="EDIT", params=action_params)
        return executor, action

    def test_cross_turn_staleness_resolved_by_reset(self):
        """
        Cross-turn scenario: user modifies file between turns.
        reset_file_hashes() clears the hash from the previous turn.
        The next EDIT should succeed because the pre-check has no stale hash.
        """
        initial_content = "Turn 1 content\n"
        modified_content = "Turn 2 modified content\n"

        fs_mock = create_autospec(IFileSystemManager)
        fs_mock.path_exists.return_value = True
        fs_mock.read_file.return_value = initial_content
        fs_mock.read_raw_file.return_value = initial_content

        executor, action = self._make_executor(fs_mock)

        # Simulate Turn 1: an EDIT action stores the hash
        log1, _ = executor.confirm_and_dispatch(
            action, interactive=False, total_actions=1
        )
        assert log1.status == ActionStatus.SUCCESS
        assert "/test/file.txt" in executor._file_hashes

        # Externally modify file (simulated by changing mock return values)
        fs_mock.read_file.return_value = modified_content
        fs_mock.read_raw_file.return_value = modified_content

        # Simulate plan execution reset (as done by orchestrator at start of each plan)
        executor.reset_file_hashes()
        assert "/test/file.txt" not in executor._file_hashes

        # Turn 2: new EDIT on same file. Without stale hash, pre-check is skipped,
        # action proceeds to dispatch_and_execute and succeeds.
        log2, _ = executor.confirm_and_dispatch(
            action, interactive=False, total_actions=1
        )
        assert log2.status == ActionStatus.SUCCESS

    def test_within_plan_detection_preserved(self):
        """
        Within the same plan, if the file is manually modified between two EDITs,
        the pre-check should still detect it and fail. The hash is NOT reset
        between actions in the same plan.
        """
        fs_mock = create_autospec(IFileSystemManager)
        fs_mock.path_exists.return_value = True
        fs_mock.read_file.return_value = "original content"
        fs_mock.read_raw_file.return_value = "original content"

        executor, action = self._make_executor(fs_mock)

        # First EDIT succeeds
        log1, _ = executor.confirm_and_dispatch(
            action, interactive=False, total_actions=2
        )
        assert log1.status == ActionStatus.SUCCESS

        # Simulate external modification within the same plan
        fs_mock.read_file.return_value = "external change"
        fs_mock.read_raw_file.return_value = "external change"

        # Second EDIT should fail because pre-check catches the change
        log2, _ = executor.confirm_and_dispatch(
            action, interactive=False, total_actions=2
        )
        assert log2.status == ActionStatus.FAILURE
        assert "content modified" in str(log2.details)
