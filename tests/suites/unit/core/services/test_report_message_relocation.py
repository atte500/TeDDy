"""Migration: MESSAGE renders as a top-level `## User Reply`, not an action."""

from datetime import datetime, timezone
from typing import Any

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

TS = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)


def _format(*logs: ActionLog) -> str:
    report = ExecutionReport(
        plan_title="Message Relocation",
        run_summary=RunSummary(status=RunStatus.SUCCESS, start_time=TS, end_time=TS),
        action_logs=list(logs),
    )
    return MarkdownReportFormatter().format(report)


def _message(details: Any) -> ActionLog:
    return ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="MESSAGE",
        params={"content": "agent text"},
        details=details,
    )


def test_message_only_report_renders_user_reply_and_skips_action_log() -> None:
    output = _format(_message("Yes, please proceed."))

    assert "## User Reply" in output
    assert "Yes, please proceed." in output
    assert "## Action Log" not in output
    assert "### `MESSAGE`" not in output
    assert "agent text" not in output


def test_message_with_mapping_content_renders_content() -> None:
    output = _format(_message({"content": "mapped reply"}))

    assert "## User Reply" in output
    assert "mapped reply" in output
    assert "## Action Log" not in output


def test_mixed_report_renders_action_log_and_user_reply() -> None:
    action = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="CREATE",
        params={"File Path": "x.py"},
    )
    output = _format(action, _message("reply here"))

    assert "## Action Log" in output
    assert "### `CREATE`: x.py" in output
    assert "## User Reply" in output
    assert "reply here" in output


def test_message_without_details_renders_no_user_reply() -> None:
    output = _format(
        ActionLog(status=ActionStatus.SUCCESS, action_type="MESSAGE", params={})
    )

    assert "## User Reply" not in output
    assert "## Action Log" not in output


def test_empty_report_renders_empty_action_log_note() -> None:
    output = _format()

    assert "## Action Log" in output
    assert "*(No actions were executed.)*" in output
    assert "## User Reply" not in output
