from datetime import datetime
from teddy_executor.core.domain.models import (
    ExecutionReport,
    RunSummary,
    RunStatus,
    ActionLog,
    ActionStatus,
)
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.services.markdown_report_formatter import (
    MarkdownReportFormatter,
)


def test_formatter_does_not_corrupt_code_block_content(container):
    """
    Ensures that whitespace sanitization does NOT collapse newlines
    inside action content (e.g., READ contents or EXECUTE stdout).
    """
    container.register(IMarkdownReportFormatter, MarkdownReportFormatter)
    formatter = container.resolve(IMarkdownReportFormatter)

    # Content with 3 newlines (2 blank lines)
    content_with_gaps = "Line 1\n\n\nLine 4"

    report = ExecutionReport(
        plan_title="Test",
        run_summary=RunSummary(
            status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
        ),
        action_logs=[
            ActionLog(
                action_type="READ",
                status=ActionStatus.SUCCESS,
                params={"Resource": "test.txt"},
                details={"content": content_with_gaps},
            )
        ],
    )

    formatted = formatter.format(report)

    assert "Line 1\n\n\nLine 4" in formatted, (
        "Content was corrupted by whitespace sanitization"
    )
