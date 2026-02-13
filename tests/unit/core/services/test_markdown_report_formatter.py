from datetime import datetime, timezone

from teddy_executor.core.domain.models.execution_report import (
    ActionLog,
    ActionStatus,
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.services.markdown_report_formatter import (
    MarkdownReportFormatter,
)


def test_formats_read_action_with_resource_contents():
    """
    Given an ExecutionReport with a successful READ action,
    When the report is formatted,
    Then the output should include a 'Resource Contents' section with the file content.
    """
    # Arrange
    formatter = MarkdownReportFormatter()
    file_content = "Hello from the file!"
    report = ExecutionReport(
        plan_title="Test Plan",
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        action_logs=[
            ActionLog(
                action_type="read",
                status=ActionStatus.SUCCESS,
                params={"Resource": "test.txt"},
                details={"content": file_content},
            )
        ],
    )

    # Act
    formatted_report = formatter.format(report)

    # Assert
    assert "## Resource Contents" in formatted_report
    assert file_content in formatted_report
    assert "**Resource:** `[test.txt](/test.txt)`" in formatted_report


def test_formats_failed_edit_action_with_file_content():
    """
    Given an ExecutionReport with a failed EDIT action containing file content in details,
    When the report is formatted,
    Then the output should include a 'Failed Action Details' section with the file content.
    """
    # Arrange
    formatter = MarkdownReportFormatter()
    file_content = "Original content of the file."
    error_message = "Permission denied."
    report = ExecutionReport(
        plan_title="Test Plan",
        run_summary=RunSummary(
            status=RunStatus.FAILURE,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        action_logs=[
            ActionLog(
                action_type="edit",
                status=ActionStatus.FAILURE,
                params={"path": "config.txt"},
                details={"error": error_message, "content": file_content},
            )
        ],
    )

    # Act
    formatted_report = formatter.format(report)

    # Assert
    assert "## Failed Action Details" in formatted_report
    assert f"- **Error:** {error_message}" in formatted_report
    assert "**Resource:** `config.txt`" in formatted_report
    assert file_content in formatted_report
