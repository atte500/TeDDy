from pathlib import Path
from unittest.mock import Mock

import pytest

from teddy_executor.core.domain.models import (
    ActionData,
    V2_ActionLog,
    V2_ExecutionReport,
    V2_Plan,
)
from teddy_executor.core.services.execution_orchestrator import (
    ExecutionOrchestrator,
)


@pytest.fixture
def mock_plan_parser():
    return Mock()


@pytest.fixture
def mock_action_dispatcher():
    return Mock()


@pytest.fixture
def mock_user_interactor():
    return Mock()


@pytest.fixture
def orchestrator(mock_plan_parser, mock_action_dispatcher, mock_user_interactor):
    return ExecutionOrchestrator(
        plan_parser=mock_plan_parser,
        action_dispatcher=mock_action_dispatcher,
        user_interactor=mock_user_interactor,
    )


def test_execute_with_failing_action(
    orchestrator,
    mock_plan_parser,
    mock_action_dispatcher,
    mock_user_interactor,
):
    """
    Given a plan with an action that fails
    When the plan is executed
    Then the final report status should be 'FAILURE'
    """
    # Arrange
    plan_path = Path("/fake/plan.yml")
    action1_params = {"name": "failing action", "details": {}}
    action1 = ActionData(type="action1", params=action1_params)
    plan = V2_Plan(actions=[action1])
    failing_log = V2_ActionLog(
        status="FAILURE",
        action_type="action1",
        params=action1_params,
        details="It broke",
    )

    mock_plan_parser.parse.return_value = plan
    mock_action_dispatcher.dispatch_and_execute.return_value = failing_log

    # Act
    report = orchestrator.execute(plan_path=plan_path, interactive=False)

    # Assert
    mock_action_dispatcher.dispatch_and_execute.assert_called_once_with(action1)
    mock_user_interactor.confirm_action.assert_not_called()
    assert report.run_summary.status == "FAILURE"
    assert report.action_logs == [failing_log]


def test_execute_interactive_and_skipped(
    orchestrator,
    mock_plan_parser,
    mock_action_dispatcher,
    mock_user_interactor,
):
    """
    Given interactive mode is enabled
    When the user denies the action
    Then the orchestrator should prompt the user but not dispatch the action
    And a 'SKIPPED' action log should be recorded
    """
    # Arrange
    plan_path = Path("/fake/plan.yml")
    action1 = ActionData(type="action1", params={})
    plan = V2_Plan(actions=[action1])

    mock_plan_parser.parse.return_value = plan
    mock_user_interactor.confirm_action.return_value = (False, "Just because")

    # Act
    report = orchestrator.execute(plan_path=plan_path, interactive=True)

    # Assert
    mock_user_interactor.confirm_action.assert_called_once()
    mock_action_dispatcher.dispatch_and_execute.assert_not_called()
    assert report.run_summary.status == "SUCCESS"
    assert len(report.action_logs) == 1
    assert report.action_logs[0].status == "SKIPPED"


def test_execute_interactive_and_approved(
    orchestrator,
    mock_plan_parser,
    mock_action_dispatcher,
    mock_user_interactor,
):
    """
    Given interactive mode is enabled
    When the user approves the action
    Then the orchestrator should prompt the user and then dispatch the action
    """
    # Arrange
    plan_path = Path("/fake/plan.yml")
    action1_params = {"name": "first action", "details": {}}
    action1 = ActionData(type="action1", params=action1_params)
    plan = V2_Plan(actions=[action1])
    action_log1 = V2_ActionLog(
        status="SUCCESS",
        action_type="action1",
        params=action1_params,
        details="Success",
    )

    mock_plan_parser.parse.return_value = plan
    mock_action_dispatcher.dispatch_and_execute.return_value = action_log1
    mock_user_interactor.confirm_action.return_value = (True, "")

    # Act
    report = orchestrator.execute(plan_path=plan_path, interactive=True)

    # Assert
    mock_user_interactor.confirm_action.assert_called_once()
    mock_action_dispatcher.dispatch_and_execute.assert_called_once_with(action1)
    assert report.run_summary.status == "SUCCESS"
    assert len(report.action_logs) == 1
    assert report.action_logs[0].status == "SUCCESS"


def test_execute_happy_path_non_interactive(
    orchestrator,
    mock_plan_parser,
    mock_action_dispatcher,
    mock_user_interactor,
):
    """
    Given a valid plan path and non-interactive mode
    When the orchestrator executes the plan
    Then it should parse the plan, dispatch all actions, and return a successful report
    And it should not interact with the user
    """
    # Arrange
    plan_path = Path("/fake/plan.yml")
    action1_params = {"name": "first action", "details": {}}
    action1 = ActionData(type="action1", params=action1_params)
    plan = V2_Plan(actions=[action1])
    action_log1 = V2_ActionLog(
        status="SUCCESS",
        action_type="action1",
        params=action1_params,
        details="Success",
    )

    mock_plan_parser.parse.return_value = plan
    mock_action_dispatcher.dispatch_and_execute.return_value = action_log1

    # Act
    report = orchestrator.execute(plan_path=plan_path, interactive=False)

    # Assert
    mock_plan_parser.parse.assert_called_once_with(plan_path)
    mock_action_dispatcher.dispatch_and_execute.assert_called_once_with(action1)
    mock_user_interactor.confirm_action.assert_not_called()

    assert isinstance(report, V2_ExecutionReport)
    assert report.run_summary.status == "SUCCESS"
    assert report.action_logs == [action_log1]
