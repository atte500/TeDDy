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
    assert "**Resource:** `[config.txt](/config.txt)`" in formatted_report
    assert file_content in formatted_report


def test_formats_action_status_on_new_line():
    """
    Given an ExecutionReport with a successful action,
    When the report is formatted,
    Then the action's header and status should be on separate lines.
    """
    # Arrange
    formatter = MarkdownReportFormatter()
    report = ExecutionReport(
        plan_title="Test Plan",
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        action_logs=[
            ActionLog(
                action_type="CREATE",
                status=ActionStatus.SUCCESS,
                params={"path": "new_file.txt"},
            )
        ],
    )

    # Act
    formatted_report = formatter.format(report)

    # Assert
    # Find the action header and assert that the *next* line is the status.
    # This is more robust than a simple substring check.
    report_lines = [line.strip() for line in formatted_report.strip().split("\n")]
    try:
        header_index = next(
            i for i, line in enumerate(report_lines) if "#### `CREATE`" in line
        )
        assert report_lines[header_index + 1] == "- **Status:**"
        # Check that the success status appears somewhere after the header
        assert "- SUCCESS" in report_lines[header_index:]
    except (StopIteration, IndexError) as e:
        assert False, (
            f"Could not find expected action header and status format. Error: {e}. Report:\n{formatted_report}"
        )


def test_report_header_has_no_extra_newlines():
    """
    Given a simple ExecutionReport,
    When the report is formatted,
    Then the 'Execution Summary' should appear immediately after the header block.
    """
    # Arrange
    formatter = MarkdownReportFormatter()
    start_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2023, 1, 1, 12, 0, 1, tzinfo=timezone.utc)
    report = ExecutionReport(
        plan_title="Test Plan",
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=start_time,
            end_time=end_time,
        ),
        action_logs=[],
    )

    # Act
    formatted_report = formatter.format(report)

    # Assert
    report_lines = [line.strip() for line in formatted_report.strip().split("\n")]

    # Assert that the summary comes right after the header block.
    # The header block consists of the H1, Overall Status, Start Time,
    # and End Time, plus surrounding blank lines.
    # We expect the summary to be at or before line index 5.
    try:
        summary_index = report_lines.index("## Execution Summary")
        assert summary_index <= 5
    except ValueError:
        assert False, "'## Execution Summary' not found in report"


def test_formats_failed_execute_action_details_human_readably():
    """
    Given an ExecutionReport with a failed EXECUTE action,
    When the report is formatted,
    Then the output should format the details in a human-readable way.
    """
    # Arrange
    formatter = MarkdownReportFormatter()
    details = {
        "stdout": "stdout message",
        "stderr": "stderr message",
        "return_code": 42,
    }
    report = ExecutionReport(
        plan_title="Test Plan",
        run_summary=RunSummary(
            status=RunStatus.FAILURE,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        action_logs=[
            ActionLog(
                action_type="execute",
                status=ActionStatus.FAILURE,
                params={"command": "a bad command"},
                details=details,
            )
        ],
    )

    # Act
    formatted_report = formatter.format(report)

    # Assert
    # Raw dictionary string should NOT be present
    assert "{'stdout':" not in formatted_report
    assert "'return_code': 42" not in formatted_report

    # Human-readable format SHOULD be present
    assert "- **Return Code:** `42`" in formatted_report
    assert "#### `stdout`" in formatted_report
    assert "```text\nstdout message\n```" in formatted_report
    assert "#### `stderr`" in formatted_report
    assert "```text\nstderr message\n```" in formatted_report
