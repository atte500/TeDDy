import pytest
from pathlib import Path
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.drivers.cli_adapter import CliTestAdapter


@pytest.mark.anyio
async def test_execute_mid_plan_failure_produces_report(real_env, monkeypatch):
    """
    Scenario: A multi-action plan where a state change causes a subsequent
    action to fail at runtime should produce a FAILURE report, not crash.
    """
    # 1. Setup workspace state
    test_file = Path(real_env.workspace) / "test.txt"
    test_file.write_text("initial content\n")
    plan_builder = MarkdownPlanBuilder(title="Mid-Plan Failure")

    adapter = CliTestAdapter(monkeypatch, real_env.workspace)

    # 2. Build a plan where EDIT is valid pre-flight but invalid after EXECUTE
    plan_markdown = (
        plan_builder.with_rationale("Reproduction of crash")
        .add_execute(
            description="Change content",
            command=f'echo "modified content" > "{test_file}"',
        )
        .add_edit(
            description="Failing edit",
            path="test.txt",
            find_replace="initial content",
            replace="new content",
        )
        .build()
    )

    # 3. Execute the plan (non-interactive)
    report = adapter.execute_plan(plan_markdown, interactive=False)

    # 4. Assertions
    # ReportParser provides access to the final status via summary and action logs
    assert report.summary.get("Overall Status") == "FAILURE"

    # First action should succeed
    logs = report.action_logs
    assert logs[0].type == "EXECUTE"
    assert logs[0].status == "SUCCESS"

    # Second action should fail but be captured in the report
    assert logs[1].type == "EDIT"
    assert logs[1].status == "FAILURE"
    assert "not found" in str(logs[1].details.get("details", "")).lower()
