import textwrap
from teddy_executor.core.domain.models import ActionStatus
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer


from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator


class FakeReviewer(IPlanReviewer):
    def __init__(self, actions_to_unselect: list[int]):
        self.actions_to_unselect = actions_to_unselect
        self.was_called = False

    def review(self, plan: Plan) -> Plan:
        self.was_called = True
        for idx in self.actions_to_unselect:
            plan.actions[idx].selected = False
        return plan


def test_orchestrator_skips_unselected_actions_integration(
    container, mock_action_dispatcher, mock_fs, mock_user_interactor
):
    # Given an orchestrator with a reviewer that unselects the second action
    fake_reviewer = FakeReviewer(actions_to_unselect=[1])
    container.register(IPlanReviewer, instance=fake_reviewer)

    # We resolve the concrete ExecutionOrchestrator to bypass SessionOrchestrator
    # and ensure it uses the mock_action_dispatcher registered in the container.
    orchestrator = container.resolve(ExecutionOrchestrator)

    plan_content = textwrap.dedent("""\
        # Partial Test
        - **Status:** Green 🟢
        - **Agent:** Developer

        ## Rationale
        ````text
        I need to create three files but skip one.
        ````

        ## Action Plan

        ### `CREATE`
        - **File Path:** [foo.py](/foo.py)
        - **Overwrite:** true
        ````python
        print("foo")
        ````

        ### `CREATE`
        - **File Path:** [bar.py](/bar.py)
        - **Overwrite:** true
        ````python
        print("bar")
        ````

        ### `CREATE`
        - **File Path:** [baz.py](/baz.py)
        - **Overwrite:** true
        ````python
        print("baz")
        ````
        """)

    # Mock the dispatcher to return success
    mock_action_dispatcher.dispatch_and_execute.return_value.status = (
        ActionStatus.SUCCESS
    )

    # Mock the user interactor to approve actions
    mock_user_interactor.confirm_action.return_value = (True, "")

    # When I run execute
    report = orchestrator.execute(plan_content=plan_content, interactive=True)

    # Then only 2 actions should be dispatched
    expected_dispatch_count = 2
    assert (
        mock_action_dispatcher.dispatch_and_execute.call_count
        == expected_dispatch_count
    )

    # And the report MUST mark the 2nd action as SKIPPED
    assert report.action_logs[0].status == ActionStatus.SUCCESS
    assert report.action_logs[1].status == ActionStatus.SKIPPED
    assert report.action_logs[2].status == ActionStatus.SUCCESS
    assert fake_reviewer.was_called
