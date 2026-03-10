import textwrap
from typer.testing import CliRunner
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.__main__ import app
from .helpers import parse_markdown_report


class FakeReviewer(IPlanReviewer):
    def __init__(self, actions_to_unselect: list[int]):
        self.actions_to_unselect = actions_to_unselect
        self.was_called = False

    def review(self, plan: Plan) -> Plan:
        self.was_called = True
        for idx in self.actions_to_unselect:
            plan.actions[idx].selected = False
        return plan


def test_partial_execution_skips_unselected_actions(tmp_path, monkeypatch, container):
    runner = CliRunner()
    # Given a plan with 3 actions
    plan_content = textwrap.dedent("""\
        # Feature Implementation
        - **Status:** Green 🟢
        - **Plan Type:** Implementation
        - **Agent:** Developer

        ## Rationale
        ````text
        I need to create three files.
        ````

        ## Action Plan

        ### `CREATE`
        - **File Path:** [foo.py](/foo.py)
        - **Description:** Create foo.
        ````python
        print("foo")
        ````

        ### `CREATE`
        - **File Path:** [bar.py](/bar.py)
        - **Description:** Create bar.
        ````python
        print("bar")
        ````

        ### `CREATE`
        - **File Path:** [baz.py](/baz.py)
        - **Description:** Create baz.
        ````python
        print("baz")
        ````
        """)

    # And a reviewer that unselects the second action (index 1)
    fake_reviewer = FakeReviewer(actions_to_unselect=[1])
    container.register(IPlanReviewer, instance=fake_reviewer)

    # When I run execute in interactive mode
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        result = runner.invoke(app, ["execute", "--plan-content", plan_content, "-y"])

    # Then only the 1st and 3rd actions must be executed
    assert result.exit_code == 0, (
        f"CLI failed with stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert (tmp_path / "foo.py").exists()
    assert not (tmp_path / "bar.py").exists()
    assert (tmp_path / "baz.py").exists()

    # And the reviewer must have been called
    assert fake_reviewer.was_called

    # And the report MUST mark the 2nd action as SKIPPED
    report = parse_markdown_report(result.stdout)
    action_logs = report["action_logs"]
    assert action_logs[0]["status"] == "SUCCESS"
    assert action_logs[1]["status"] == "SKIPPED"
    assert "deselected" in action_logs[1]["details"]["error"].lower()
    assert action_logs[2]["status"] == "SUCCESS"
