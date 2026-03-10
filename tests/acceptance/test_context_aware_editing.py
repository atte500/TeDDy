import textwrap
from typer.testing import CliRunner
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.__main__ import app
from .helpers import parse_markdown_report


class ModifyingFakeReviewer(IPlanReviewer):
    """
    A fake reviewer that modifies the plan based on a provided function.
    """

    def __init__(self, modifier_func):
        self.modifier_func = modifier_func
        self.was_called = False

    def review(self, plan: Plan) -> Plan:
        self.was_called = True
        return self.modifier_func(plan)


def test_context_aware_editing_modifies_create_action(tmp_path, monkeypatch, container):
    runner = CliRunner()

    # Given a plan with a CREATE action
    plan_content = textwrap.dedent("""\
        # Edit Test
        - **Status:** Green 🟢
        - **Plan Type:** Implementation
        - **Agent:** Developer

        ## Rationale
        ````text
        Initial plan to create foo.py.
        ````

        ## Action Plan

        ### `CREATE`
        - **File Path:** [foo.py](/foo.py)
        - **Description:** Create foo.
        ````python
        print("original content")
        ````
        """)

    # And a reviewer that changes the path to bar.py and modifies the content
    def modify_create_action(plan: Plan) -> Plan:
        action = plan.actions[0]
        # The parser maps "File Path" to "path"
        action.params["path"] = "bar.py"
        action.params["content"] = 'print("modified content")\n'
        return plan

    fake_reviewer = ModifyingFakeReviewer(modify_create_action)
    container.register(IPlanReviewer, instance=fake_reviewer)

    # When I run execute in interactive mode
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        result = runner.invoke(app, ["execute", "--plan-content", plan_content, "-y"])

    # Then the final execution MUST create bar.py with the modified content
    assert result.exit_code == 0, f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    assert (tmp_path / "bar.py").exists()
    assert (tmp_path / "bar.py").read_text() == 'print("modified content")\n'

    # And foo.py MUST NOT exist
    assert not (tmp_path / "foo.py").exists()

    # And the report MUST reflect the executed action (the modified one)
    report = parse_markdown_report(result.stdout)
    action_logs = report["action_logs"]
    # The report parser extracts keys from the Markdown labels.
    # For CREATE/EDIT, 'path' is rendered as 'File Path'.
    assert action_logs[0]["params"]["File Path"] == "bar.py"
