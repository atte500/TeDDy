import pytest
from unittest.mock import MagicMock
from teddy_executor.core.domain.models import Plan, ActionData, ActionLog, ActionStatus
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator


@pytest.fixture
def orchestrator(
    container, mock_action_dispatcher, mock_report_formatter, mock_user_interactor
):
    # Register core components needed for orchestrator
    container.register(ExecutionOrchestrator)
    # We mock the validator to skip pre-flight checks in this logic test
    mock_validator = MagicMock(spec=IPlanValidator)
    mock_validator.validate.return_value = []
    container.register(IPlanValidator, instance=mock_validator)

    return container.resolve(ExecutionOrchestrator)


def test_orchestrator_populates_report_metadata(orchestrator, mock_action_dispatcher):
    # Setup test data
    action = ActionData(
        type="READ", params={"resource": "test.txt"}, description="test"
    )
    plan = Plan(title="Test Plan Title", rationale="Test Rationale", actions=[action])

    # Mock successful dispatch
    mock_action_dispatcher.dispatch_and_execute.return_value = ActionLog(
        status=ActionStatus.SUCCESS, action_type="READ", params={"resource": "test.txt"}
    )

    # Execute
    report = orchestrator.execute(plan, interactive=False)

    # Assert metadata flow
    assert report.plan_title == "Test Plan Title"
    assert report.rationale == "Test Rationale"
    assert report.original_actions == [action]
