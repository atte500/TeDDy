from datetime import datetime

from teddy_executor.core.domain.models import (
    ExecutionReport,
    RunSummary,
    RunStatus,
    ActionLog,
    ActionStatus,
)
from teddy_executor.core.services.markdown_report_formatter import (
    MarkdownReportFormatter,
)


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
