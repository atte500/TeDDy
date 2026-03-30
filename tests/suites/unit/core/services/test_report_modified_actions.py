from datetime import datetime
from teddy_executor.core.domain.models.execution_report import (
    ExecutionReport,
    RunSummary,
    RunStatus,
    ActionLog,
    ActionStatus,
)
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)


def test_report_renders_modified_tag_for_actions(container):
    # Setup: Create a report with one modified action
    formatter = container.resolve(IMarkdownReportFormatter)

    summary = RunSummary(
        status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
    )

    # Setup: Create a report with one modified action
    log = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="EDIT",
        params={"File Path": "test.py"},
        modified=True,
    )

    report = ExecutionReport(
        run_summary=summary, plan_title="Modified Test", action_logs=[log]
    )

    # Act
    output = formatter.format(report)

    # Assert
    assert "### `EDIT` (modified): [test.py](/test.py)" in output
