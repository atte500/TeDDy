from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.core.domain.models import Plan


class ModifyingFakeReviewer(IPlanReviewer):
    """A fake reviewer that modifies the plan based on a provided function."""

    def __init__(self, modifier_func):
        self.modifier_func = modifier_func

    def review(self, plan: Plan) -> Plan:
        return self.modifier_func(plan)

    def review_action(self, action, total_actions, agent_name=None):
        return True

    def review_plan(self, plan):
        return plan


def test_context_aware_editing_modifies_create_action(tmp_path, monkeypatch):
    """Scenario: Verify that interactive plan modifications are executed and reported."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_filesystem()

    # Define a reviewer that changes the path to bar.py and modifies the content
    def modify_create_action(plan: Plan) -> Plan:
        action = plan.actions[0]
        # ActionDispatcher/Executor uses "path" internally after normalization
        action.params.pop("File Path", None)
        action.params["path"] = "bar.py"
        action.params["content"] = 'print("modified content")\n'
        return plan

    fake_reviewer = ModifyingFakeReviewer(modify_create_action)
    env.container.register(IPlanReviewer, instance=fake_reviewer)

    adapter = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Edit Test")
        .add_create("foo.py", 'print("original content")')
        .build()
    )

    # When I run execute in interactive mode
    # (Note: adapter.execute_plan defaults to interactive=False, so we must be explicit)
    report = adapter.execute_plan(plan, interactive=True)

    # Then the final execution MUST create bar.py with the modified content
    assert (tmp_path / "bar.py").exists()
    assert (tmp_path / "bar.py").read_text() == 'print("modified content")\n'

    # And foo.py MUST NOT exist
    assert not (tmp_path / "foo.py").exists()

    # And the report MUST reflect the executed action (the modified one)
    assert report.action_logs[0].params["File Path"] == "bar.py"
