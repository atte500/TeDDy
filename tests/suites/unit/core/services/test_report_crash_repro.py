from datetime import datetime, timezone
import pytest
from teddy_executor.core.domain.models.execution_report import (
    ActionLog,
    ActionStatus,
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.services.markdown_report_formatter import (
    MarkdownReportFormatter,
)


@pytest.fixture
def formatter(container):
    container.register(IMarkdownReportFormatter, MarkdownReportFormatter)
    return container.resolve(IMarkdownReportFormatter)


def test_formatter_crashes_when_details_is_string(formatter):
    """
    Given an ActionLog where details is a string (not a dict),
    When the report is formatted,
    Then it should not raise an UndefinedError.
    """
    # Arrange
    report = ExecutionReport(
        plan_title="Crash Repro",
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        action_logs=[
            ActionLog(
                action_type="TEST",
                status=ActionStatus.SKIPPED,
                params={"foo": "bar"},
                details="This is a string detail, not a dict.",
            )
        ],
    )

    # Act
    # This should not raise
    output = formatter.format(report)

    # Assert
    assert "This is a string detail" in output
