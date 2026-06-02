import pytest
from datetime import datetime
from teddy_executor.core.domain.models import ExecutionReport, RunSummary, RunStatus
from teddy_executor.core.services.markdown_report_formatter import (
    MarkdownReportFormatter,
)


@pytest.fixture
def formatter():
    return MarkdownReportFormatter()


def test_report_encapsulates_user_message_in_fences(formatter):
    """
    Ensures that the user request (message) in an execution report
    is wrapped in 6-tilde fences for safety and readability.
    """
    summary = RunSummary(
        status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
    )
    report = ExecutionReport(
        plan_title="Test Plan",
        run_summary=summary,
        user_request="I want to fix *this* and `that`.",
        action_logs=[],
    )

    markdown = formatter.format(report)

    # Check that the message is present and wrapped in fences
    # Note: Content uses triple backticks since it only contains single backticks.
    expected_fragment = "## User Request\n```text\nI want to fix *this* and `that`."
    assert expected_fragment in markdown


def test_report_handles_missing_user_message(formatter):
    """
    Ensures that if no user message is present, the section is omitted.
    """
    summary = RunSummary(
        status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
    )
    report = ExecutionReport(
        plan_title="Test Plan", run_summary=summary, user_request=None, action_logs=[]
    )

    markdown = formatter.format(report)
    assert "## User Request" not in markdown
