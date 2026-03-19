from teddy_executor.core.domain.models import (
    ActionData,
    ActionLog,
    ActionStatus,
    Plan,
    RunStatus,
)
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator


def test_execute_with_failing_action(
    env, mock_action_dispatcher, mock_plan_parser, mock_user_interactor
):
    """
    Given a plan with an action that fails
    When the plan is executed
    Then the final report status should be 'FAILURE'
    """
    # Arrange
    orchestrator = env.get_service(ExecutionOrchestrator)

    action1_params = {"command": "exit 1", "description": "failing action"}
    action1 = ActionData(type="EXECUTE", params=action1_params)
    plan = Plan(title="Test Plan", rationale="Test", actions=[action1])
    failing_log = ActionLog(
        status=ActionStatus.FAILURE,
        action_type="action1",
        params=action1_params,
        details="It broke",
    )

    mock_action_dispatcher.dispatch_and_execute.return_value = failing_log

    # Act
    report = orchestrator.execute(plan=plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.FAILURE
    mock_plan_parser.parse.assert_not_called()
    mock_action_dispatcher.dispatch_and_execute.assert_called_once_with(
        action1, agent_name=None
    )
    mock_user_interactor.confirm_action.assert_not_called()


def test_execute_interactive_and_skipped(
    env, mock_user_interactor, mock_action_dispatcher
):
    """
    Given interactive mode is enabled
    When the user denies the action
    Then the orchestrator should prompt the user but not dispatch the action
    And a 'SKIPPED' action log should be recorded
    """
    # Arrange
    orchestrator = env.get_service(ExecutionOrchestrator)

    action1 = ActionData(type="EXECUTE", params={"command": "ls"})
    plan = Plan(title="Test Plan", rationale="Test", actions=[action1])

    mock_user_interactor.confirm_action.return_value = (False, "Just because")

    # Act
    report = orchestrator.execute(plan=plan, interactive=True)

    # Assert
    # A plan where all actions are skipped should have an overall status of SKIPPED.
    assert report.run_summary.status == RunStatus.SKIPPED
    assert len(report.action_logs) == 1
    assert report.action_logs[0].status == ActionStatus.SKIPPED
    mock_user_interactor.confirm_action.assert_called_once()
    mock_action_dispatcher.dispatch_and_execute.assert_not_called()


def test_execute_with_mixed_success_and_skipped_is_success(
    env, mock_user_interactor, mock_action_dispatcher
):
    """
    Given a plan where one action succeeds and one is skipped
    When the plan is executed
    Then the final report status should be 'SUCCESS'
    """
    # Arrange
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
    mock_user_interactor.confirm_action.side_effect = [(True, ""), (False, "skip")]
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
    env, mock_user_interactor, mock_action_dispatcher
):
    """
    Given interactive mode is enabled
    When the user approves the action
    Then the orchestrator should prompt the user and then dispatch the action
    """
    # Arrange
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
    mock_user_interactor.confirm_action.return_value = (True, "")

    # Act
    report = orchestrator.execute(plan=plan, interactive=True)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    mock_user_interactor.confirm_action.assert_called_once()
    mock_action_dispatcher.dispatch_and_execute.assert_called_once_with(
        action1, agent_name=None
    )


def test_execute_auto_skips_after_failure(env, mock_action_dispatcher):
    """
    Given a plan with two actions
    When the first action fails during execution
    Then the second action should not be dispatched
    And the second action's log should indicate it was skipped due to a previous failure
    And the overall status should be FAILURE
    """
    # Arrange
    orchestrator = env.get_service(ExecutionOrchestrator)

    action1 = ActionData(
        type="EXECUTE", params={"command": "ls"}, description="First Action"
    )
    action2 = ActionData(
        type="EXECUTE", params={"command": "ls"}, description="Second Action"
    )
    plan = Plan(title="Test Plan", rationale="Test", actions=[action1, action2])

    failing_log = ActionLog(
        status=ActionStatus.FAILURE,
        action_type="action1",
        params={},
        details="It broke",
    )

    # We shouldn't reach the second dispatch, but if we do, return success to highlight the failure
    success_log = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="action2",
        params={},
        details="Should not happen",
    )

    mock_action_dispatcher.dispatch_and_execute.side_effect = [failing_log, success_log]

    # Act
    report = orchestrator.execute(plan=plan, interactive=False)

    # Assert
    expected_action_count = 2
    assert report.run_summary.status == RunStatus.FAILURE
    assert len(report.action_logs) == expected_action_count

    # First action failed
    assert report.action_logs[0].status == ActionStatus.FAILURE

    # Second action should be skipped
    assert report.action_logs[1].status == ActionStatus.SKIPPED
    assert "Skipped because a previous action failed." in str(
        report.action_logs[1].details
    )

    # Dispatcher should only be called once
    mock_action_dispatcher.dispatch_and_execute.assert_called_once_with(
        action1, agent_name=None
    )


def test_execute_continues_on_failure_if_allow_failure_is_true(
    env, mock_action_dispatcher
):
    """
    Given a plan with an action that has allow_failure=True,
    When that action fails,
    Then the subsequent actions should still be executed.
    """
    # Arrange
    orchestrator = env.get_service(ExecutionOrchestrator)

    action1 = ActionData(
        type="EXECUTE",
        description="Action 1",
        params={"command": "fail", "allow_failure": True},
    )
    action2 = ActionData(
        type="EXECUTE", description="Action 2", params={"command": "echo success"}
    )
    plan = Plan(title="Test Plan", rationale="Test", actions=[action1, action2])

    failing_log = ActionLog(
        status=ActionStatus.FAILURE,
        action_type="EXECUTE",
        params={"command": "fail", "allow_failure": True},
        details="Fail",
    )
    success_log = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="EXECUTE",
        params={"command": "echo success"},
        details="Success",
    )

    mock_action_dispatcher.dispatch_and_execute.side_effect = [failing_log, success_log]

    # Act
    report = orchestrator.execute(plan=plan, interactive=False)

    # Assert
    expected_action_count = 2
    assert report.run_summary.status == RunStatus.FAILURE
    assert len(report.action_logs) == expected_action_count
    assert report.action_logs[0].status == ActionStatus.FAILURE
    assert report.action_logs[1].status == ActionStatus.SUCCESS


def test_execute_happy_path_non_interactive(
    env, mock_plan_parser, mock_action_dispatcher, mock_user_interactor
):
    """
    Given a valid plan path and non-interactive mode
    When the orchestrator executes the plan
    Then it should parse the plan, dispatch all actions, and return a successful report
    And it should not interact with the user
    """
    # Arrange
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

    # Act
    report = orchestrator.execute(plan=plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    assert len(report.action_logs) == 1
    assert report.action_logs[0] == action_log1
    mock_plan_parser.parse.assert_not_called()
    mock_action_dispatcher.dispatch_and_execute.assert_called_once_with(
        action1, agent_name=None
    )
    mock_user_interactor.confirm_action.assert_not_called()
