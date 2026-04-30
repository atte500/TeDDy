import pytest
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


@pytest.mark.anyio
async def test_execution_report_shows_user_modified_fields(env):
    """
    Scenario: User modified field tracking
    Given a plan with an EXECUTE action
    When the action is modified in the reviewer (simulated)
    Then the execution report should contain the (user modified: ...) indicator
    """
    # 1. Build a plan
    plan_content = (
        MarkdownPlanBuilder("Audit Trail Test")
        .with_rationale("Verify modified fields are reported.")
        .add_execute("ls -la", description="List files")
        .build()
    )

    # 2. Setup Mock Reviewer to modify the action
    # We mock the review() method to return a plan where the action is modified.
    from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer

    mock_reviewer = env.mock_port(IPlanReviewer)

    def simulate_review(plan):
        action = plan.actions[0]
        action.params["command"] = "ls -R"  # Modification
        action.modified = True
        action.modified_fields = ["command"]
        return plan

    mock_reviewer.review.side_effect = simulate_review
    mock_reviewer.review_action.return_value = (True, "")

    # 3. Execute the plan
    from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase

    orchestrator = env.container.resolve(IRunPlanUseCase)

    report = orchestrator.execute(plan_content=plan_content, interactive=True)

    # 4. Verify the report object
    assert report.action_logs[0].modified is True
    assert "command" in report.action_logs[0].modified_fields

    # 5. Verify the formatted Markdown report
    from teddy_executor.core.ports.outbound.markdown_report_formatter import (
        IMarkdownReportFormatter,
    )

    formatter = env.container.resolve(IMarkdownReportFormatter)
    markdown_report = formatter.format(report)

    assert "### `EXECUTE` (user modified: command)" in markdown_report
