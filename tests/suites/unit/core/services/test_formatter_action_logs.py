from datetime import datetime, timezone

from teddy_executor.core.domain.models import WebSearchResults
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
from tests.harness.observers.report_parser import ReportParser


def _get_report(action_logs=None, status=RunStatus.SUCCESS, validation_result=None):
    return ExecutionReport(
        plan_title="Test Plan",
        run_summary=RunSummary(
            status=status,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        action_logs=action_logs or [],
        validation_result=validation_result,
    )


def test_formats_read_action_with_resource_contents():
    """Verify READ action with Resource Contents section."""
    formatter = MarkdownReportFormatter()
    content = "Hello from the file!"
    report = _get_report(
        [
            ActionLog(
                status=ActionStatus.SUCCESS,
                action_type="read",
                params={"Resource": "test.txt"},
                details={"content": content},
            )
        ]
    )

    parser = ReportParser(formatter.format(report))

    assert parser.extract_resource_contents()["test.txt"] == content
    assert parser.action_logs[0].params["File Path"] == "test.txt"


def test_formats_failed_edit_action_with_file_content():
    """Verify failed EDIT action includes original file content in Resource Contents."""
    formatter = MarkdownReportFormatter()
    content = "Original content."
    report = _get_report(
        [
            ActionLog(
                status=ActionStatus.FAILURE,
                action_type="edit",
                params={"path": "config.txt"},
                details={"content": content},
            )
        ]
    )

    parser = ReportParser(formatter.format(report))

    assert parser.action_logs[0].status == "FAILURE"
    assert parser.extract_resource_contents()["config.txt"] == content


def test_formats_action_status_inline():
    """Verify status is rendered in the action block."""
    formatter = MarkdownReportFormatter()
    report = _get_report(
        [
            ActionLog(
                status=ActionStatus.SUCCESS,
                action_type="CREATE",
                params={"path": "new.txt"},
            )
        ]
    )

    parser = ReportParser(formatter.format(report))

    assert parser.action_logs[0].status == "SUCCESS"


def test_formats_multiline_execute_command_correctly():
    """Verify multiline command rendering in EXECUTE."""
    formatter = MarkdownReportFormatter()
    cmd = "git add .\ngit commit"
    report = _get_report(
        [
            ActionLog(
                status=ActionStatus.SUCCESS,
                action_type="EXECUTE",
                params={"command": cmd, "expected_outcome": "OK"},
            )
        ]
    )

    output = formatter.format(report)

    assert f"- **Command:**\n```shell\n{cmd}\n```" in output


def test_formats_failed_execute_action_details():
    """Verify failed EXECUTE details (stdout/stderr/rc)."""
    formatter = MarkdownReportFormatter()
    details = {"stdout": "out", "stderr": "err", "return_code": 42}
    report = _get_report(
        [
            ActionLog(
                status=ActionStatus.FAILURE,
                action_type="execute",
                params={"command": "bad"},
                details=details,
            )
        ]
    )

    parser = ReportParser(formatter.format(report))

    assert parser.action_logs[0].details["stdout"] == "out"
    assert parser.action_logs[0].details["stderr"] == "err"
    expected_code = 42
    assert parser.action_logs[0].details["return_code"] == expected_code


def test_formats_research_action_with_results():
    """Verify RESEARCH action result rendering."""
    formatter = MarkdownReportFormatter()
    results: WebSearchResults = {
        "query_results": [
            {"query": "q", "results": [{"title": "T", "href": "H", "body": "B"}]}
        ]
    }
    report = _get_report(
        [
            ActionLog(
                status=ActionStatus.SUCCESS,
                action_type="RESEARCH",
                params={"Description": "Res"},
                details=results,
            )
        ]
    )

    output = formatter.format(report)

    assert "**Query:** `q`" in output
    assert "[T](H)" in output
    assert "B" in output


def test_formats_validation_failed_report():
    """Verify VALIDATION_FAILED report includes errors."""
    formatter = MarkdownReportFormatter()
    errors = ["E1", "E2"]
    report = _get_report(status=RunStatus.VALIDATION_FAILED, validation_result=errors)

    output = formatter.format(report)

    assert "## Validation Errors" in output
    assert "E1" in output
    assert "E2" in output


def test_formats_research_action_with_content():
    """Verify RESEARCH action result rendering prioritizes content over body."""
    formatter = MarkdownReportFormatter()
    results: WebSearchResults = {
        "query_results": [
            {
                "query": "q",
                "results": [
                    {
                        "title": "T",
                        "href": "H",
                        "body": "B",
                        "content": "Full extracted content",
                    }
                ],
            }
        ]
    }
    report = _get_report(
        [
            ActionLog(
                status=ActionStatus.SUCCESS,
                action_type="RESEARCH",
                params={"Description": "Res"},
                details=results,
            )
        ]
    )

    output = formatter.format(report)

    assert "**Query:** `q`" in output
    assert "[T](H)" in output
    assert "```Content\nFull extracted content\n```" in output
    assert "```Snippet" not in output
    assert "B" not in output
