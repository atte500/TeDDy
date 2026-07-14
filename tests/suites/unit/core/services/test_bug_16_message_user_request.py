"""
Regression test for Bug 16: MESSAGE action reply should not populate
the User Request section in the report. The user_request field should
only be populated by:
1. The `message` parameter passed to `ExecutionOrchestrator.execute()` (TUI `m` key).
2. Non-MESSAGE action captured_messages (TUI `m` during review).

MESSAGE action replies belong exclusively in action_log.details.
"""
from unittest.mock import MagicMock

from teddy_executor.core.domain.models import (
    ActionData,
    ActionLog,
    ActionStatus,
    Plan,
)
from teddy_executor.core.domain.models.orchestrator_ports import OrchestratorPorts
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator


class TestMessageActionUserRequest:
    """Tests that MESSAGE action replies do not leak into user_request."""

    def test_message_action_does_not_set_user_request(self):
        """MESSAGE action's captured_message should NOT be stored in plan.metadata["user_request"]."""
        ports = MagicMock(spec=OrchestratorPorts)
        mock_executor = MagicMock()
        ports.action_executor = mock_executor
        ports.plan_parser = MagicMock()
        ports.plan_validator = MagicMock()
        ports.plan_validator.validate.return_value = []
        ports.file_system_manager = MagicMock()
        ports.report_assembler = MagicMock()
        ports.user_interactor = MagicMock()
        ports.plan_reviewer = None

        orchestrator = ExecutionOrchestrator(ports)

        msg_action = ActionData(
            type="MESSAGE",
            params={"message": "What do you think?"},
            description="LLM asks user",
            selected=True,
        )
        plan = Plan(
            title="Test Plan",
            rationale="Testing MESSAGE reply",
            actions=[msg_action],
            metadata={},
        )
        fake_log = ActionLog(
            status=ActionStatus.SUCCESS,
            action_type="MESSAGE",
            params={},
            details="User reply: I think this is great!",
        )
        orchestrator._action_executor.confirm_and_dispatch.return_value = (
            fake_log,
            "User reply: I think this is great!",
        )
        orchestrator._action_executor.reset_file_hashes.return_value = None

        action_log, should_halt = orchestrator._handle_action_in_loop(
            msg_action, plan, interactive=False, halt_execution=False
        )

        assert "user_request" not in plan.metadata, (
            f"MESSAGE action should not set user_request, but got: "
            f"'{plan.metadata.get('user_request')}'"
        )
        assert action_log.details == "User reply: I think this is great!"
        assert action_log.status == ActionStatus.SUCCESS

    def test_non_message_action_still_sets_user_request(self):
        """Non-MESSAGE actions should still store captured_message in user_request."""
        ports = MagicMock(spec=OrchestratorPorts)
        mock_executor = MagicMock()
        ports.action_executor = mock_executor
        ports.plan_parser = MagicMock()
        ports.plan_validator = MagicMock()
        ports.plan_validator.validate.return_value = []
        ports.file_system_manager = MagicMock()
        ports.report_assembler = MagicMock()
        ports.user_interactor = MagicMock()
        ports.plan_reviewer = None

        orchestrator = ExecutionOrchestrator(ports)

        create_action = ActionData(
            type="CREATE",
            params={"path": "/tmp/test.txt", "content": "hello"},
            description="Create test file",
            selected=True,
        )
        plan = Plan(
            title="Test Plan",
            rationale="Testing CREATE user_request",
            actions=[create_action],
            metadata={},
        )
        fake_log = ActionLog(
            status=ActionStatus.SUCCESS,
            action_type="CREATE",
            params={"path": "/tmp/test.txt"},
            details="Created",
        )
        orchestrator._action_executor.confirm_and_dispatch.return_value = (
            fake_log,
            "User approved via m key",
        )
        orchestrator._action_executor.reset_file_hashes.return_value = None

        orchestrator._handle_action_in_loop(
            create_action, plan, interactive=False, halt_execution=False
        )

        assert plan.metadata.get("user_request") == "User approved via m key", (
            f"Non-MESSAGE action should set user_request, got: "
            f"'{plan.metadata.get('user_request')}'"
        )

    def test_empty_captured_message_does_not_set_user_request(self):
        """When captured_message is empty, user_request should not be set regardless of action type."""
        ports = MagicMock(spec=OrchestratorPorts)
        mock_executor = MagicMock()
        ports.action_executor = mock_executor
        ports.plan_parser = MagicMock()
        ports.plan_validator = MagicMock()
        ports.plan_validator.validate.return_value = []
        ports.file_system_manager = MagicMock()
        ports.report_assembler = MagicMock()
        ports.user_interactor = MagicMock()
        ports.plan_reviewer = None

        orchestrator = ExecutionOrchestrator(ports)

        execute_action = ActionData(
            type="EXECUTE",
            params={"command": "echo hello"},
            description="Execute test",
            selected=True,
        )
        plan = Plan(
            title="Test Plan",
            rationale="Testing empty captured_message",
            actions=[execute_action],
            metadata={},
        )
        fake_log = ActionLog(
            status=ActionStatus.SUCCESS,
            action_type="EXECUTE",
            params={"command": "echo hello"},
            details="hello",
        )
        orchestrator._action_executor.confirm_and_dispatch.return_value = (
            fake_log,
            "",  # empty captured_message
        )
        orchestrator._action_executor.reset_file_hashes.return_value = None

        orchestrator._handle_action_in_loop(
            execute_action, plan, interactive=False, halt_execution=False
        )

        assert "user_request" not in plan.metadata, (
            "user_request should not be set when captured_message is empty"
        )