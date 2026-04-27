from unittest.mock import MagicMock
from teddy_executor.core.services.markdown_report_formatter import (
    MarkdownReportFormatter,
)
from teddy_executor.core.domain.models import (
    ExecutionReport,
    RunSummary,
    RunStatus,
    ActionData,
    ActionLog,
    ActionStatus,
)
from datetime import datetime


def test_formatter_passes_is_concise_to_template():
    formatter = MarkdownReportFormatter()
    # Mock the template render method to capture arguments
    formatter.template.render = MagicMock(return_value="rendered")

    summary = RunSummary(
        status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
    )
    report = ExecutionReport(run_summary=summary)

    formatter.format(report, is_concise=False)

    # Check that is_concise was in the context passed to render
    args, kwargs = formatter.template.render.call_args
    context = args[0]
    assert context["is_concise"] is False

    formatter.format(report, is_concise=True)
    args, kwargs = formatter.template.render.call_args
    context = args[0]
    assert context["is_concise"] is True


def test_formatter_passes_is_session_to_template():
    formatter = MarkdownReportFormatter()
    # Mock the template render method to capture arguments
    formatter.template.render = MagicMock(return_value="rendered")

    summary = RunSummary(
        status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
    )
    report = ExecutionReport(run_summary=summary, is_session=True)

    formatter.format(report)

    # Check that is_session was in the context passed to render
    args, kwargs = formatter.template.render.call_args
    context = args[0]
    assert context["is_session"] is True


def test_formatter_renders_rationale_only_when_not_concise():
    formatter = MarkdownReportFormatter()
    summary = RunSummary(
        status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
    )
    report = ExecutionReport(
        run_summary=summary,
        plan_title="Test Plan",
        rationale="SECRET_RATIONALE_CONTENT",
    )

    # Comprehensive mode
    comprehensive_report = formatter.format(report, is_concise=False)
    assert "SECRET_RATIONALE_CONTENT" in comprehensive_report
    assert "## Rationale" in comprehensive_report

    # Concise mode
    concise_report = formatter.format(report, is_concise=True)
    assert "SECRET_RATIONALE_CONTENT" not in concise_report
    assert "## Rationale" not in concise_report


def test_formatter_renders_original_actions_only_when_not_concise():
    formatter = MarkdownReportFormatter()
    summary = RunSummary(
        status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
    )
    action = ActionData(
        type="EXECUTE", params={"command": "ls"}, description="list files"
    )
    report = ExecutionReport(
        run_summary=summary, plan_title="Test Plan", original_actions=[action]
    )

    # Comprehensive mode
    comprehensive_report = formatter.format(report, is_concise=False)
    assert "## Original Action Plan" in comprehensive_report
    assert "list files" in comprehensive_report

    # Concise mode
    concise_report = formatter.format(report, is_concise=True)
    assert "## Original Action Plan" not in concise_report


def test_formatter_sanitizes_whitespace():
    """
    Ensures the formatter strips leading/trailing whitespace and collapses
    3+ newlines into 2.
    """
    formatter = MarkdownReportFormatter()
    # Mock the template to return a string with excessive whitespace and newlines
    formatter.template.render = MagicMock(
        return_value="\n\n  # Header\n\n\n\nContent  \n\n\nFooter\n\n  "
    )

    summary = RunSummary(
        status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
    )
    report = ExecutionReport(run_summary=summary)

    formatted = formatter.format(report)

    # 1. Stripped leading/trailing
    assert formatted.startswith("# Header")
    assert formatted.endswith("Footer")

    # 2. Collapsed newlines
    assert "\n\n\n" not in formatted
    # Check intermediate parts
    assert "# Header\n\nContent" in formatted
    assert "Content\n\nFooter" in formatted


def test_formatter_hides_resource_contents_in_session_mode():
    formatter = MarkdownReportFormatter()
    summary = RunSummary(
        status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
    )

    # Log with content (e.g., from a READ action)
    log = ActionLog(
        action_type="READ",
        params={"resource": "test.py"},
        status=ActionStatus.SUCCESS,
        details={"content": "print('hello')"},
    )

    # 1. Non-session mode: Should show Resource Contents
    report_normal = ExecutionReport(
        run_summary=summary, action_logs=[log], is_session=False
    )
    output_normal = formatter.format(report_normal, is_concise=True)
    assert "## Resource Contents" in output_normal
    assert "test.py" in output_normal
    assert "print('hello')" in output_normal

    # 2. Session mode: Should HIDE Resource Contents
    report_session = ExecutionReport(
        run_summary=summary, action_logs=[log], is_session=True
    )
    output_session = formatter.format(report_session, is_concise=True)
    assert "## Resource Contents" not in output_session
    assert "print('hello')" not in output_session
    # The action log entry should still exist
    assert "### `READ`: [test.py](/test.py)" in output_session
