from tests.harness.setup.mocking import POSIXPathMock
from teddy_executor.core.domain.models.plan import Plan, ActionData, ExecutionStatus
from teddy_executor.core.domain.models.execution_report import ActionLog, ActionStatus
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
from teddy_executor.core.services.execution_report_assembler import (
    ExecutionReportAssembler,
)


def test_orchestrator_skips_manually_executed_actions():
    # Setup
    mock_parser = POSIXPathMock()
    mock_validator = POSIXPathMock()
    mock_validator.validate.return_value = []
    mock_executor = POSIXPathMock()
    mock_fs = POSIXPathMock()

    orchestrator = ExecutionOrchestrator(
        plan_parser=mock_parser,
        plan_validator=mock_validator,
        action_executor=mock_executor,
        file_system_manager=mock_fs,
        report_assembler=ExecutionReportAssembler(),
        user_interactor=POSIXPathMock(),
    )

    # Create an action that was ALREADY executed
    persisted_log = ActionLog(
        status=ActionStatus.SUCCESS, action_type="CREATE", params={"path": "test.txt"}
    )
    action = ActionData(
        type="CREATE",
        params={"path": "test.txt"},
        executed=True,
        state=ExecutionStatus.SUCCESS,
        action_log=persisted_log,
    )

    plan = Plan(title="Test", rationale="Test", actions=[action])

    # Execute
    report = orchestrator.execute(plan=plan, interactive=False)

    # Verify
    assert len(report.action_logs) == 1
    assert report.action_logs[0] == persisted_log
    # Confirm ActionExecutor was NEVER called for this action
    mock_executor.confirm_and_dispatch.assert_not_called()


def test_orchestrator_halts_on_manual_failure():
    # Create a failed manual action
    persisted_log = ActionLog(
        status=ActionStatus.FAILURE, action_type="EXECUTE", params={"command": "fail"}
    )
    failed_action = ActionData(
        type="EXECUTE",
        params={"command": "fail"},
        executed=True,
        state=ExecutionStatus.FAILURE,
        action_log=persisted_log,
    )
    pending_action = ActionData(type="CREATE", params={"path": "next.txt"})

    plan = Plan(title="Test", rationale="Test", actions=[failed_action, pending_action])

    mock_executor = POSIXPathMock()
    mock_executor.handle_skipped_action.side_effect = lambda action, reason: ActionLog(
        status=ActionStatus.SKIPPED,
        action_type=action.type,
        params=action.params,
        details=reason,
    )
    mock_validator = POSIXPathMock()
    mock_validator.validate.return_value = []
    orchestrator = ExecutionOrchestrator(
        POSIXPathMock(),
        mock_validator,
        mock_executor,
        POSIXPathMock(),
        ExecutionReportAssembler(),
        POSIXPathMock(),
    )

    report = orchestrator.execute(plan=plan, interactive=False)

    expected_action_count = 2
    assert len(report.action_logs) == expected_action_count
    assert report.action_logs[0].status == ActionStatus.FAILURE
    assert report.action_logs[1].status == ActionStatus.SKIPPED
    assert "previous action failed" in report.action_logs[1].details
