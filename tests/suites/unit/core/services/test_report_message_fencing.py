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


def test_message_action_shows_content_in_fenced_codeblock(formatter):
    """
    Ensures that a MESSAGE action's content is rendered in a fenced code block
    under "- **User Reply:**" in the Action Log.
    """
    from teddy_executor.core.domain.models import ActionLog, ActionStatus

    summary = RunSummary(
        status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
    )
    action_log = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="MESSAGE",
        params={"Description": "Message to user"},
        details={"content": "This is the reply text"},
    )
    report = ExecutionReport(
        plan_title="Test Plan",
        run_summary=summary,
        user_request=None,
        action_logs=[action_log],
    )

    markdown = formatter.format(report)

    # Check the Action Log section contains the expected elements
    assert "### `MESSAGE`:" in markdown
    assert "**User Reply:**" in markdown
    assert "This is the reply text" in markdown
    # Check it's inside a code fence (content has no backticks, so fence is triple backticks)
    assert (
        "```\nThis is the reply text\n```" in markdown
        or "```text\nThis is the reply text\n```" in markdown
    )


def test_message_action_with_backticks_in_content_uses_safe_fence(formatter):
    """
    Ensures that if the message content contains backticks, the fence length
    is adjusted to avoid ambiguity.
    """
    from teddy_executor.core.domain.models import ActionLog, ActionStatus

    summary = RunSummary(
        status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
    )
    action_log = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="MESSAGE",
        params={"Description": "Message with code"},
        details={"content": "Use `code` and ```fenced``` blocks here"},
    )
    report = ExecutionReport(
        plan_title="Test Plan",
        run_summary=summary,
        user_request=None,
        action_logs=[action_log],
    )

    markdown = formatter.format(report)

    # Content has triple backticks, so fence must be at least 4 backticks
    assert "**User Reply:**" in markdown
    assert "Use `code` and ```fenced``` blocks here" in markdown
    # The fence surrounding the content should be longer than the longest internal backtick sequence (3)
    assert "````\nUse `code` and ```fenced``` blocks here\n````" in markdown
