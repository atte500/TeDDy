from unittest.mock import MagicMock
from teddy_executor.core.domain.models import Plan, ActionData, ActionStatus
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
from teddy_executor.core.services.action_executor import ActionExecutor


def test_orchestrator_skips_non_isolated_terminal_action():
    """
    Scenario 2: Terminal Action is skipped in multi-action plan
    """
    # Arrange
    plan_parser = MagicMock()
    action_dispatcher = MagicMock()
    user_interactor = MagicMock()
    file_system_manager = MagicMock()
    edit_simulator = MagicMock()

    action_executor = ActionExecutor(
        action_dispatcher=action_dispatcher,
        user_interactor=user_interactor,
        file_system_manager=file_system_manager,
        edit_simulator=edit_simulator,
        config_service=MagicMock(),
    )
    mock_validator = MagicMock()
    mock_validator.validate.return_value = []
    orchestrator = ExecutionOrchestrator(
        plan_parser=plan_parser,
        plan_validator=mock_validator,
        action_executor=action_executor,
        file_system_manager=file_system_manager,
    )

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

    # Mock successful execution of the first action
    action_dispatcher.dispatch_and_execute.return_value = MagicMock(
        status=ActionStatus.SUCCESS, action_type="CREATE", params={}, details=""
    )

    # Mock user approval
    user_interactor.confirm_action.return_value = (True, "")

    # Act
    report = orchestrator.execute(plan=plan, interactive=True)

    # Assert
    expected_count = 2
    assert len(report.action_logs) == expected_count

    # First action should be success
    assert report.action_logs[0].action_type == "CREATE"
    assert report.action_logs[0].status == ActionStatus.SUCCESS

    # Second action (PROMPT) should be SKIPPED because it's not isolated
    assert report.action_logs[1].action_type == "PROMPT"
    assert report.action_logs[1].status == ActionStatus.SKIPPED
    assert "Action must be executed in isolation" in report.action_logs[1].details
