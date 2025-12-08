import pytest

from teddy.core.domain.models import (
    CommandResult,
    Action,
    Plan,
    ActionResult,
    ExecutionReport,
)


def test_command_result_instantiation():
    """
    Tests that a CommandResult can be instantiated with valid data.
    """
    # ARRANGE
    stdout = "output"
    stderr = "error"
    return_code = 1

    # ACT
    result = CommandResult(stdout=stdout, stderr=stderr, return_code=return_code)

    # ASSERT
    assert result.stdout == stdout
    assert result.stderr == stderr
    assert result.return_code == return_code


def test_execute_action_raises_error_on_missing_command():
    """
    Tests that an 'execute' action raises ValueError if 'command' param is missing.
    """
    with pytest.raises(
        ValueError, match="'execute' action requires a 'command' parameter"
    ):
        Action(action_type="execute", params={"other_param": "value"})


def test_execute_action_raises_error_on_empty_command():
    """
    Tests that an 'execute' action raises ValueError if 'command' param is empty.
    """
    with pytest.raises(ValueError, match="'command' parameter cannot be empty"):
        Action(action_type="execute", params={"command": ""})


def test_action_raises_error_on_empty_action_type():
    """
    Tests that instantiating an Action with an empty action_type raises a ValueError.
    """
    with pytest.raises(ValueError, match="action_type must be a non-empty string"):
        Action(action_type="", params={"command": "echo"})


def test_plan_raises_error_on_empty_actions_list():
    """
    Tests that a Plan cannot be instantiated with an empty list of actions.
    """
    with pytest.raises(ValueError, match="Plan must contain at least one action"):
        Plan(actions=[])


def test_action_result_raises_error_on_invalid_status():
    """
    Tests that ActionResult raises a ValueError on an invalid status.
    """
    action = Action(action_type="execute", params={"command": "test"})
    with pytest.raises(ValueError, match="Status must be one of"):
        ActionResult(action=action, status="INVALID_STATUS", output=None, error=None)


def test_action_result_instantiation():
    """
    Tests that an ActionResult can be instantiated with valid data.
    """
    # ARRANGE
    action = Action(action_type="execute", params={"command": "test"})
    status = "SUCCESS"
    output = "some output"
    error = None

    # ACT
    result = ActionResult(action=action, status=status, output=output, error=error)

    # ASSERT
    assert result.action == action
    assert result.status == status
    assert result.output == output
    assert result.error == error


def test_execution_report_instantiation():
    """
    Tests that an ExecutionReport can be instantiated with valid data.
    """
    # ARRANGE
    run_summary = {"status": "SUCCESS"}
    environment = {"os": "test_os"}
    action_logs = [
        ActionResult(
            action=Action(action_type="execute", params={"command": "test"}),
            status="SUCCESS",
            output="ok",
            error=None,
        )
    ]

    # ACT
    report = ExecutionReport(
        run_summary=run_summary, environment=environment, action_logs=action_logs
    )

    # ASSERT
    assert report.run_summary == run_summary
    assert report.environment == environment
    assert report.action_logs == action_logs


def test_plan_instantiation():
    """
    Tests that a Plan can be instantiated with a list of actions.
    """
    # ARRANGE
    action1 = Action(action_type="execute", params={"command": "ls"})
    actions = [action1]

    # ACT
    plan = Plan(actions=actions)

    # ASSERT
    assert plan.actions == actions


def test_action_instantiation():
    """
    Tests that an Action can be instantiated with valid data for 'execute'.
    """
    # ARRANGE
    action_type = "execute"
    params = {"command": "echo 'hello'"}

    # ACT
    action = Action(action_type=action_type, params=params)

    # ASSERT
    assert action.action_type == action_type
    assert action.params == params
