import contextlib
import logging
import threading

from teddy_executor.core.domain.models import (
    ActionData,
    ActionLog,
    ActionStatus,
    Plan,
    RunStatus,
)
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
from teddy_executor.core.utils.interrupt_guard import INTERRUPT_REASON


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
    report = orchestrator.execute(plan=plan, require_approval=False)

    # Assert
    assert report.run_summary.status == RunStatus.FAILURE
    mock_plan_parser.parse.assert_not_called()
    mock_action_dispatcher.dispatch_and_execute.assert_called_once_with(
        action1, agent_name=None
    )
    mock_user_interactor.confirm_action.assert_not_called()


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
    report = orchestrator.execute(plan=plan, require_approval=False)

    # Assert
    expected_action_count = 2
    assert report.run_summary.status == RunStatus.FAILURE
    assert len(report.action_logs) == expected_action_count

    # First action failed
    assert report.action_logs[0].status == ActionStatus.FAILURE

    # Second action should be skipped
    assert report.action_logs[1].status == ActionStatus.SKIPPED
    assert (
        "Skipped because a previous action failed. (Hint: use 'Allow Failure: true' in EXECUTE actions to proceed even with non-zero exit codes.)"
        in str(report.action_logs[1].details)
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
    report = orchestrator.execute(plan=plan, require_approval=False)

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
    report = orchestrator.execute(plan=plan, require_approval=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    assert len(report.action_logs) == 1
    assert report.action_logs[0] == action_log1
    mock_plan_parser.parse.assert_not_called()
    mock_action_dispatcher.dispatch_and_execute.assert_called_once_with(
        action1, agent_name=None
    )
    mock_user_interactor.confirm_action.assert_not_called()


def test_aborted_plan_preserves_manually_executed_logs(env, mock_plan_reviewer):
    """
    Given a plan reviewed interactively (via TUI),
    When the user manually executes one action (e.g. via 'x') but then quits/aborts ('q'),
    Then the ExecutionReport should preserve the ActionLog of the executed action,
    And the final status should reflect the executed action instead of defaulting to SKIPPED.
    """
    # Arrange
    orchestrator = env.get_service(ExecutionOrchestrator)
    orchestrator._plan_reviewer = mock_plan_reviewer

    action1 = ActionData(type="READ", params={"file": "foo.txt"}, description="Act 1")
    action2 = ActionData(type="READ", params={"file": "bar.txt"}, description="Act 2")
    plan = Plan(title="Test Plan", rationale="Test", actions=[action1, action2])

    def mock_review_side_effect(p: Plan, **kwargs) -> None:
        _ = kwargs
        # Simulate manual execution of action 1 before quitting
        act = p.actions[0]
        act.executed = True
        act.action_log = ActionLog(
            status=ActionStatus.SUCCESS,
            action_type="READ",
            params=act.params,
            details="Manually harvested log",
        )

    mock_plan_reviewer.review.side_effect = mock_review_side_effect

    # Act
    report = orchestrator.execute(plan=plan, require_approval=True)

    # Assert
    assert len(report.action_logs) == 2
    assert report.action_logs[0].status == ActionStatus.SUCCESS
    assert report.action_logs[0].details == "Manually harvested log"

    assert report.action_logs[1].status == ActionStatus.SKIPPED
    assert "Execution aborted by user." in report.action_logs[1].details

    # The run is now explicitly marked as ABORTED even if some actions were successful
    assert report.run_summary.status == RunStatus.ABORTED
    assert report.plan_title == "Test Plan"


def test_execute_with_single_message_bypasses_reviewer(
    env, mock_plan_parser, mock_plan_reviewer, mock_action_dispatcher
):
    """
    Scenario: Communication turns (MESSAGE) bypass approval for fluid conversation.
    """
    # Arrange
    orchestrator = env.get_service(ExecutionOrchestrator)
    orchestrator._plan_reviewer = mock_plan_reviewer

    action = ActionData(type="MESSAGE", params={"content": "Hello from Message"})
    plan = Plan(title="Test Plan", rationale="Test", actions=[action])

    success_log = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="MESSAGE",
        params=action.params,
        details="Message success",
    )
    mock_action_dispatcher.dispatch_and_execute.return_value = success_log

    # Act
    orchestrator.execute(plan=plan, require_approval=True)

    # Assert
    # Verify reviewer.review (TUI) was NOT called
    mock_plan_reviewer.review.assert_not_called()


def test_manual_then_batch_orders_report_by_execution_sequence(
    env, mock_action_dispatcher
):
    """A hand-executed action reports first, before the actions that ran after it."""
    # Arrange
    orchestrator = env.get_service(ExecutionOrchestrator)
    manual_log = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="EXECUTE",
        params={"command": "manual"},
    )
    manual_action = ActionData(
        type="EXECUTE",
        params={"command": "manual"},
        description="manual step",
        executed=True,
        action_log=manual_log,
        execution_sequence=1,
    )
    batch_action = ActionData(
        type="EXECUTE", params={"command": "batch"}, description="batch step"
    )
    plan = Plan(
        title="Ordering Plan", rationale="Test", actions=[batch_action, manual_action]
    )
    mock_action_dispatcher.dispatch_and_execute.return_value = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="EXECUTE",
        params={"command": "batch"},
    )

    # Act
    report = orchestrator.execute(plan=plan, require_approval=False)

    # Assert
    assert [log.params["command"] for log in report.action_logs] == [
        "manual",
        "batch",
    ]


def test_preexecuted_console_lines_follow_execution_sequence(env, caplog):
    """Console lines name hand-executed actions in the order they actually ran."""
    # Arrange
    orchestrator = env.get_service(ExecutionOrchestrator)
    orchestrator_logger = "teddy_executor.core.services.execution_orchestrator"
    ran_second = ActionData(
        type="EXECUTE",
        params={"command": "b"},
        description="ran second",
        executed=True,
        action_log=ActionLog(
            status=ActionStatus.SUCCESS, action_type="EXECUTE", params={"command": "b"}
        ),
        execution_sequence=2,
    )
    ran_first = ActionData(
        type="EXECUTE",
        params={"command": "a"},
        description="ran first",
        executed=True,
        action_log=ActionLog(
            status=ActionStatus.SUCCESS, action_type="EXECUTE", params={"command": "a"}
        ),
        execution_sequence=1,
    )
    plan = Plan(title="Manual Order", rationale="Test", actions=[ran_second, ran_first])

    # Act
    with caplog.at_level(logging.INFO):
        orchestrator.execute(plan=plan, require_approval=False)

    # Assert
    lines = [
        record.getMessage()
        for record in caplog.records
        if record.name == orchestrator_logger
    ]
    assert lines == [
        "EXECUTE - ran first",
        "SUCCESS",
        "EXECUTE - ran second",
        "SUCCESS",
    ]


def test_unstamped_manual_action_keeps_plan_position(env, mock_action_dispatcher):
    """An action carrying no stamp stays where it sits instead of sorting forward."""
    # Arrange
    orchestrator = env.get_service(ExecutionOrchestrator)
    legacy_action = ActionData(
        type="EXECUTE",
        params={"command": "legacy"},
        description="legacy step",
        executed=True,
        action_log=ActionLog(
            status=ActionStatus.SUCCESS,
            action_type="EXECUTE",
            params={"command": "legacy"},
        ),
    )
    batch_action = ActionData(
        type="EXECUTE", params={"command": "batch"}, description="batch step"
    )
    plan = Plan(
        title="Legacy Plan", rationale="Test", actions=[legacy_action, batch_action]
    )
    mock_action_dispatcher.dispatch_and_execute.return_value = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="EXECUTE",
        params={"command": "batch"},
    )

    # Act
    report = orchestrator.execute(plan=plan, require_approval=False)

    # Assert
    assert [log.params["command"] for log in report.action_logs] == [
        "legacy",
        "batch",
    ]


class _SetInterruptGuard:
    """In-memory fake guard whose drain flag is already set.

    The loop reads the flag at the top of every iteration, so a pre-set flag
    reproduces a signal that arrived while an earlier action was in flight,
    without installing any real signal handler.
    """

    def __init__(self) -> None:
        self.interrupted = threading.Event()
        self.interrupted.set()

    @contextlib.contextmanager
    def enter_executing(self):
        """Yields the executing scope the orchestrator enters around the loop."""
        yield


def test_deselected_and_halted_actions_are_announced(
    env, mock_action_dispatcher, mock_user_interactor
):
    """Each skip the orchestrator causes is named to the user with its reason."""
    orchestrator = env.get_service(ExecutionOrchestrator)

    deselected = ActionData(type="CREATE", params={"path": "a.txt"}, selected=False)
    failing = ActionData(type="EXECUTE", params={"command": "fail"})
    halted = ActionData(type="CREATE", params={"path": "b.txt"})
    plan = Plan(title="Skips", rationale="Test", actions=[deselected, failing, halted])
    mock_action_dispatcher.dispatch_and_execute.return_value = ActionLog(
        status=ActionStatus.FAILURE,
        action_type="EXECUTE",
        params={"command": "fail"},
    )

    orchestrator.execute(plan=plan, require_approval=False)

    announced = [
        (call.args[0].type, call.args[1])
        for call in mock_user_interactor.notify_skipped_action.call_args_list
    ]
    assert [action_type for action_type, _reason in announced] == [
        "CREATE",
        "CREATE",
    ]
    assert "deselected" in announced[0][1]
    assert "previous action failed" in announced[1][1]


def test_interrupt_drain_announces_every_remaining_action(env, mock_user_interactor):
    """Actions the two-phase interrupt drain skips are named with the reason."""
    orchestrator = env.get_service(ExecutionOrchestrator)
    orchestrator._interrupt_guard = _SetInterruptGuard()

    plan = Plan(
        title="Interrupted",
        rationale="Test",
        actions=[ActionData(type="CREATE", params={"path": "a.txt"})],
    )

    orchestrator.execute(plan=plan, require_approval=False)

    announced = [
        call.args[1]
        for call in mock_user_interactor.notify_skipped_action.call_args_list
    ]
    assert announced == [INTERRUPT_REASON]


def test_skipped_message_action_stays_silent(env, mock_user_interactor):
    """A skipped MESSAGE turn is not announced, matching the dispatcher."""
    orchestrator = env.get_service(ExecutionOrchestrator)

    plan = Plan(
        title="Message",
        rationale="Test",
        actions=[ActionData(type="MESSAGE", params={"content": "hi"}, selected=False)],
    )

    report = orchestrator.execute(plan=plan, require_approval=False)

    assert report.action_logs[0].status == ActionStatus.SKIPPED
    mock_user_interactor.notify_skipped_action.assert_not_called()
