import pytest
from unittest.mock import MagicMock
from teddy_executor.core.domain.models import Plan, ActionData, ActionStatus, ActionLog
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator


@pytest.fixture
def orchestrator(
    container, mock_action_dispatcher, mock_user_interactor
):
    container.register(ExecutionOrchestrator)
    mock_validator = MagicMock(spec=IPlanValidator)
    mock_validator.validate.return_value = []
    container.register(IPlanValidator, instance=mock_validator)
    return container.resolve(ExecutionOrchestrator)


def test_orchestrator_allows_non_isolated_terminal_action(
    orchestrator, mock_action_dispatcher, mock_user_interactor
):
    """
    Scenario: Terminal Action is allowed in multi-action plan
    """
    # Arrange
    # A multi-action plan: CREATE then PROMPT
    actions = [
        ActionData(
            type="CREATE",
            description="test",
            params={"path": "test.txt", "content": ""},
        ),
        ActionData(type="PROMPT", description="confirm", params={"prompt": "Confirm?"}),
    ]
    plan = Plan(title="Multi-action", rationale="Test", actions=actions, metadata={})

    # Mock successful execution of actions
    def dispatch_side_effect(action, **_kwargs):
        return ActionLog(
            status=ActionStatus.SUCCESS,
            action_type=action.type,
            params={},
            details="",
        )

    mock_action_dispatcher.dispatch_and_execute.side_effect = dispatch_side_effect

    # Mock user approval
    mock_user_interactor.confirm_action.return_value = (True, "")

    # Act
    report = orchestrator.execute(plan=plan, interactive=True)

    # Assert
    expected_action_count = 2
    assert len(report.action_logs) == expected_action_count

    # First action should be success
    assert report.action_logs[0].action_type == "CREATE"
    assert report.action_logs[0].status == ActionStatus.SUCCESS

    # Second action (PROMPT) should be SUCCESS because isolation is relaxed
    assert report.action_logs[1].action_type == "PROMPT"
    assert report.action_logs[1].status == ActionStatus.SUCCESS
