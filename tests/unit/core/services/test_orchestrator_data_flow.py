from unittest.mock import MagicMock
from teddy_executor.core.domain.models import Plan, ActionData, ActionLog, ActionStatus
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator


def test_orchestrator_populates_report_metadata():
    # Setup mocks
    parser = MagicMock()
    dispatcher = MagicMock()
    interactor = MagicMock()
    fs = MagicMock()
    simulator = MagicMock()

    orchestrator = ExecutionOrchestrator(parser, dispatcher, interactor, fs, simulator)

    # Setup test data
    action = ActionData(
        type="READ", params={"resource": "test.txt"}, description="test"
    )
    plan = Plan(title="Test Plan Title", rationale="Test Rationale", actions=[action])

    # Mock successful dispatch
    dispatcher.dispatch_and_execute.return_value = ActionLog(
        status=ActionStatus.SUCCESS, action_type="READ", params={"resource": "test.txt"}
    )

    # Execute
    report = orchestrator.execute(plan, interactive=False)

    # Assert metadata flow
    assert report.plan_title == "Test Plan Title"
    assert report.rationale == "Test Rationale"
    assert report.original_actions == [action]
