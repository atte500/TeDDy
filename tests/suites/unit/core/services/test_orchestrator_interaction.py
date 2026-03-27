from teddy_executor.core.domain.models import (
    ActionData,
    ActionLog,
    ActionStatus,
    Plan,
    RunStatus,
)
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
from unittest.mock import patch
from teddy_executor.core.services.action_executor import ActionExecutor
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer


def test_orchestrator_delegates_to_reviewer_in_interactive_mode(
    env, mock_plan_reviewer, mock_action_dispatcher
):
    """
    Given interactive mode is enabled and a plan reviewer is present
    When the orchestrator processes actions
    Then it should call review_action on the reviewer for each action
    """
    # Arrange
    env.container.register(IPlanReviewer, instance=mock_plan_reviewer)
    orchestrator = env.get_service(ExecutionOrchestrator)

    action1 = ActionData(type="EXECUTE", params={"command": "ls"})
    plan = Plan(title="Test Plan", rationale="Test", actions=[action1])

    # Reviewer approves
    mock_plan_reviewer.review_action.return_value = (True, "")

    success_log = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="EXECUTE",
        params={"command": "ls"},
        details="Success",
    )
    mock_action_dispatcher.dispatch_and_execute.return_value = success_log

    # Act
    orchestrator.execute(plan=plan, interactive=True)

    # Assert
    mock_plan_reviewer.review_action.assert_called_once_with(
        action1, 1, agent_name=None
    )


def test_orchestrator_falls_back_to_legacy_interaction_if_no_reviewer(
    env, mock_action_dispatcher
):
    """
    Given interactive mode is enabled but NO plan reviewer is present
    When the orchestrator processes actions
    Then it should call confirm_and_dispatch with interactive=True
    """
    # Arrange
    # Manually instantiate orchestrator WITHOUT a reviewer
    from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
    from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
    from teddy_executor.core.ports.outbound import IFileSystemManager

    orchestrator = ExecutionOrchestrator(
        plan_parser=env.container.resolve(IPlanParser),
        plan_validator=env.container.resolve(IPlanValidator),
        action_executor=env.container.resolve(ActionExecutor),
        file_system_manager=env.container.resolve(IFileSystemManager),
        plan_reviewer=None,
    )

    action1 = ActionData(type="EXECUTE", params={"command": "ls"})
    plan = Plan(title="Test Plan", rationale="Test", actions=[action1])

    # We need to mock ActionExecutor.confirm_and_dispatch since we're testing the orchestrator's call to it
    with patch.object(ActionExecutor, "confirm_and_dispatch") as mock_confirm:
        mock_confirm.return_value = (
            ActionLog(
                status=ActionStatus.SUCCESS,
                action_type="EXECUTE",
                params={},
                details="",
            ),
            "",
        )

        # Act
        orchestrator.execute(plan=plan, interactive=True)

        # Assert
        mock_confirm.assert_called_once_with(
            action1,
            interactive=True,
            total_actions=1,
            agent_name=None,
            is_session=False,
        )


def test_execute_interactive_and_skipped(
    env, mock_plan_reviewer, mock_action_dispatcher
):
    """
    Given interactive mode is enabled
    When the user denies the action via the reviewer
    Then the orchestrator should not dispatch the action
    And a 'SKIPPED' action log should be recorded
    """
    # Arrange
    # Ensure the container has the mock_plan_reviewer fixture's version
    env.container.register(IPlanReviewer, instance=mock_plan_reviewer)
    orchestrator = env.get_service(ExecutionOrchestrator)

    action1 = ActionData(type="EXECUTE", params={"command": "ls"})
    plan = Plan(title="Test Plan", rationale="Test", actions=[action1])

    mock_plan_reviewer.review_action.return_value = (False, "")

    # Act
    report = orchestrator.execute(plan=plan, interactive=True)

    # Assert
    # A plan where all actions are skipped should have an overall status of SKIPPED.
    assert report.run_summary.status == RunStatus.SKIPPED
    assert len(report.action_logs) == 1
    assert report.action_logs[0].status == ActionStatus.SKIPPED
    mock_plan_reviewer.review_action.assert_called_once()
    mock_action_dispatcher.dispatch_and_execute.assert_not_called()


def test_execute_with_mixed_success_and_skipped_is_success(
    env, mock_plan_reviewer, mock_action_dispatcher
):
    """
    Given a plan where one action succeeds and one is skipped via the reviewer
    When the plan is executed
    Then the final report status should be 'SUCCESS'
    """
    # Arrange
    env.container.register(IPlanReviewer, instance=mock_plan_reviewer)
    orchestrator = env.get_service(ExecutionOrchestrator)

    action1 = ActionData(type="EXECUTE", params={"command": "ls"})
    action2 = ActionData(type="EXECUTE", params={"command": "pwd"})
    plan = Plan(title="Test Plan", rationale="Test", actions=[action1, action2])
    success_log = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="action1",
        params={},
        details="Success",
    )

    # User approves first action, skips second
    mock_plan_reviewer.review_action.side_effect = [(True, ""), (False, "")]
    mock_action_dispatcher.dispatch_and_execute.return_value = success_log

    # Act
    report = orchestrator.execute(plan=plan, interactive=True)

    # Assert
    expected_action_count = 2
    assert report.run_summary.status == RunStatus.SUCCESS
    assert len(report.action_logs) == expected_action_count
    assert report.action_logs[0].status == ActionStatus.SUCCESS
    assert report.action_logs[1].status == ActionStatus.SKIPPED
    mock_action_dispatcher.dispatch_and_execute.assert_called_once_with(
        action1, agent_name=None
    )


def test_execute_interactive_and_approved(
    env, mock_plan_reviewer, mock_action_dispatcher
):
    """
    Given interactive mode is enabled
    When the user approves the action via the reviewer
    Then the orchestrator should dispatch the action
    """
    # Arrange
    # Ensure the container has the mock_plan_reviewer fixture's version
    env.container.register(IPlanReviewer, instance=mock_plan_reviewer)
    orchestrator = env.get_service(ExecutionOrchestrator)

    action1_params = {"command": "ls", "description": "first action"}
    action1 = ActionData(type="EXECUTE", params=action1_params)
    plan = Plan(title="Test Plan", rationale="Test", actions=[action1])
    action_log1 = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="action1",
        params=action1_params,
        details="Success",
    )

    mock_action_dispatcher.dispatch_and_execute.return_value = action_log1
    mock_plan_reviewer.review_action.return_value = (True, "")

    # Act
    report = orchestrator.execute(plan=plan, interactive=True)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    mock_plan_reviewer.review_action.assert_called_once()
    mock_action_dispatcher.dispatch_and_execute.assert_called_once_with(
        action1, agent_name=None
    )
