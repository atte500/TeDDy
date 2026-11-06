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

RESEARCH_HINT = "*Hint: Use READ on a result URL to fetch the page contents.*"


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
    """Verify multiline command rendering for a reviewer-modified EXECUTE."""
    formatter = MarkdownReportFormatter()
    cmd = "git add .\ngit commit"
    report = _get_report(
        [
            ActionLog(
                status=ActionStatus.SUCCESS,
                action_type="EXECUTE",
                params={"command": cmd, "expected_outcome": "OK"},
                modified_fields=["command"],
            )
        ]
    )

    output = formatter.format(report)

    assert f"- **Command:**\n```shell\n{cmd}\n```" in output


def test_unmodified_successful_execute_omits_command_block():
    """A successful EXECUTE whose command matches the plan omits the command block."""
    formatter = MarkdownReportFormatter()
    report = _get_report(
        [
            ActionLog(
                status=ActionStatus.SUCCESS,
                action_type="EXECUTE",
                params={"command": "echo hi", "expected_outcome": "prints hi"},
            )
        ]
    )

    output = formatter.format(report)

    assert "- **Command:**" not in output
    assert "- **Expected Outcome:** prints hi" in output


def test_modified_execute_renders_inline_command_block():
    """A reviewer-edited command stays visible so the deviation remains auditable."""
    formatter = MarkdownReportFormatter()
    report = _get_report(
        [
            ActionLog(
                status=ActionStatus.SUCCESS,
                action_type="EXECUTE",
                params={"command": "echo hi"},
                modified_fields=["command"],
            )
        ]
    )

    output = formatter.format(report)

    assert "- **Command:** `echo hi`" in output


def test_failed_execute_renders_inline_command_block():
    """A failed EXECUTE keeps the executed command for diagnosis."""
    formatter = MarkdownReportFormatter()
    report = _get_report(
        [
            ActionLog(
                status=ActionStatus.FAILURE,
                action_type="EXECUTE",
                params={"command": "exit 1"},
                details={"return_code": 1},
            )
        ]
    )

    output = formatter.format(report)

    assert "- **Command:** `exit 1`" in output


def test_failed_multiline_execute_renders_fenced_command_block():
    """A failed multiline command keeps the fenced form."""
    formatter = MarkdownReportFormatter()
    cmd = "git add .\ngit commit"
    report = _get_report(
        [
            ActionLog(
                status=ActionStatus.FAILURE,
                action_type="EXECUTE",
                params={"command": cmd},
                details={"return_code": 1},
            )
        ]
    )

    output = formatter.format(report)

    assert f"- **Command:**\n```shell\n{cmd}\n```" in output


def test_failed_execute_without_command_renders_no_command_block():
    """A missing command parameter never renders a command block, even on failure."""
    formatter = MarkdownReportFormatter()
    report = _get_report(
        [
            ActionLog(
                status=ActionStatus.FAILURE,
                action_type="EXECUTE",
                params={"expected_outcome": "nothing to run"},
            )
        ]
    )

    output = formatter.format(report)

    assert "- **Command:**" not in output


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
    """Verify RESEARCH action result rendering with the refined layout."""
    formatter = MarkdownReportFormatter()
    results: WebSearchResults = {
        "query_results": [
            {"query": "q", "results": [{"title": "T", "href": "H", "description": "B"}]}
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

    assert '#### SERP for "q"' in output
    assert "1. `H`" in output
    assert "   - **Title:** T" in output
    assert "   - **Description:** B" in output


def test_formats_validation_failed_report():
    """Verify VALIDATION_FAILED report includes errors."""
    formatter = MarkdownReportFormatter()
    errors = ["E1", "E2"]
    report = _get_report(status=RunStatus.VALIDATION_FAILED, validation_result=errors)

    output = formatter.format(report)

    assert "## Validation Errors" in output
    assert "E1" in output
    assert "E2" in output


def test_research_query_without_results_renders_no_results_note():
    """An empty query renders the no-results note and suppresses the hint."""
    formatter = MarkdownReportFormatter()
    results = {"query_results": [{"query": "empty", "results": []}]}
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

    assert '#### SERP for "empty"' in output
    assert "*(No results returned.)*" in output
    assert RESEARCH_HINT not in output


def test_research_query_missing_results_key_renders_no_results_note():
    """A query entry without a results key renders the no-results note."""
    formatter = MarkdownReportFormatter()
    results = {"query_results": [{"query": "missing"}]}
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

    assert '#### SERP for "missing"' in output
    assert "*(No results returned.)*" in output


def test_research_partial_results_render_hint_when_any_query_has_results():
    """A result in any query keeps the hint visible even if another query is empty."""
    formatter = MarkdownReportFormatter()
    results = {
        "query_results": [
            {"query": "a", "results": []},
            {
                "query": "b",
                "results": [{"title": "T", "href": "H", "description": "B"}],
            },
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

    assert "*(No results returned.)*" in output
    assert RESEARCH_HINT in output


def test_research_empty_title_and_description_bullets_are_omitted():
    """A result with empty title and description keeps only its link."""
    formatter = MarkdownReportFormatter()
    results = {
        "query_results": [
            {
                "query": "q",
                "results": [{"title": "", "href": "H", "description": ""}],
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

    assert "1. `H`" in output
    assert "- **Title:**" not in output
    assert "- **Description:**" not in output
    assert RESEARCH_HINT in output
