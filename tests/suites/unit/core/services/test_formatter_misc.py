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

    # Assert that the Action Log comes right after the header block.
    # The header block consists of the H1, Overall Status, Start Time,
    # and End Time, plus surrounding blank lines.
    # We expect the log to be at or before line index 10 (increased for rationale section).
    max_header_lines = 10
    try:
        summary_index = report_lines.index("## Action Log")
        assert summary_index <= max_header_lines
    except ValueError:
        assert False, "'## Action Log' not found in report"


def test_formatter_smart_fencing_stdout():
    """
    Given an ExecutionReport with an action log containing QUAD backticks in stdout,
    When format() is called,
    Then the rendered markdown should use a fence of at least 5 backticks for that block.
    """
    # GIVEN
    formatter = MarkdownReportFormatter()

    # Content contains quad backticks, which would break a fixed quad-backtick fence
    stdout_content = "Some output\n````\nmore output\n````"

    log = ActionLog(
        action_type="EXECUTE",
        params={"Description": "Test Command"},
        status=ActionStatus.SUCCESS,
        details={"stdout": stdout_content, "return_code": 0},
    )

    report = ExecutionReport(
        run_summary=RunSummary(
            status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
        ),
        plan_title="Test Plan",
        action_logs=[log],
    )

    # WHEN
    result = formatter.format(report)

    # THEN
    # We expect a code block fenced with 5 backticks
    assert "`````text" in result
    assert stdout_content in result
    assert "`````" in result


def test_formatter_smart_fencing_resource_content():
    """
    Given an ExecutionReport with a failed EDIT action where the file content has backticks,
    When format() is called,
    Then the Resource Contents section should use a smart fence.
    """
    # GIVEN
    formatter = MarkdownReportFormatter()

    file_content = "def foo():\n    ```docstring```\n    pass"

    log = ActionLog(
        action_type="EDIT",
        params={"File Path": "src/foo.py"},
        status=ActionStatus.FAILURE,
        details={"error": "Failed", "content": file_content},
    )

    report = ExecutionReport(
        run_summary=RunSummary(
            status=RunStatus.FAILURE, start_time=datetime.now(), end_time=datetime.now()
        ),
        plan_title="Test Plan",
        action_logs=[log],
        failed_resources={"src/foo.py": file_content},
    )

    # WHEN
    result = formatter.format(report)

    # THEN
    # We expect the Resource Contents section to be fenced correctly
    assert (
        "````text" in result or "````python" in result
    )  # Depending on if language detection works
    assert file_content in result


def test_read_action_uses_mapped_language_tags():
    """
    Given a READ action for a file with an extension that should be mapped (e.g., .cfg -> ini),
    When the report is formatted,
    Then the code block should use the mapped language tag.
    """
    formatter = MarkdownReportFormatter()
    report = ExecutionReport(
        plan_title="Test",
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        action_logs=[
            ActionLog(
                action_type="read",
                status=ActionStatus.SUCCESS,
                params={"Resource": "config.cfg"},
                details={"content": "debug=true"},
            )
        ],
    )

    output = formatter.format(report)

    # Mapped extension check: .cfg should be rendered as ```ini
    assert "```ini\ndebug=true\n```" in output
