"""Regression tests for report content render placement.

Contract under test: a successful READ action's content must render EXACTLY
ONCE in the generated execution report, in both session and non-session
(execute) modes:

- Full READ (no ``lines`` param): rendered under ``## Resource Contents``
  (non-session only) with the "Up-to-date contents" note.
- Line-scoped READ (``lines`` param): rendered inline inside its Action Log
  entry, with no ``## Resource Contents`` section and no note.
- Failed action with content: rendered under ``## Resource Contents``
  (non-session only).
"""

from datetime import datetime, timezone

from teddy_executor.core.domain.models import (
    ActionLog,
    ActionStatus,
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.services.markdown_report_formatter import (
    MarkdownReportFormatter,
)

SENTINEL = "REPORT-RENDER-PLACEMENT-SENTINEL"
CONTENT = f"line-before\n{SENTINEL}\nline-after"


def _build_report(action_logs: list[ActionLog], is_session: bool) -> ExecutionReport:
    return ExecutionReport(
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 1, 12, 0, 1, tzinfo=timezone.utc),
        ),
        plan_title="Report Render Placement Regression",
        rationale="Locks the READ content render-placement contract.",
        user_request=None,
        is_session=is_session,
        metadata={},
        original_actions=[],
        action_logs=action_logs,
    )


def _format(action_logs: list[ActionLog], is_session: bool) -> str:
    return MarkdownReportFormatter().format(_build_report(action_logs, is_session))


def _line_scoped_read_log() -> ActionLog:
    return ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="READ",
        params={"File Path": "docs/spec.md", "lines": "1-3"},
        details={"content": CONTENT},
    )


def _full_read_log() -> ActionLog:
    return ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="READ",
        params={"File Path": "docs/spec.md"},
        details={"content": CONTENT},
    )


def test_line_scoped_read_renders_exactly_once_in_execute_mode():
    output = _format([_line_scoped_read_log()], is_session=False)
    assert output.count(SENTINEL) == 1
    assert "## Resource Contents" not in output


def test_line_scoped_read_renders_exactly_once_in_session_mode():
    output = _format([_line_scoped_read_log()], is_session=True)
    assert output.count(SENTINEL) == 1
    assert "## Resource Contents" not in output


def test_full_read_renders_in_resource_contents_in_execute_mode():
    output = _format([_full_read_log()], is_session=False)
    assert output.count(SENTINEL) == 1
    assert "## Resource Contents" in output
    assert "Up-to-date contents are provided under `Resource Contents`" in output


def test_full_read_renders_no_resource_contents_in_session_mode():
    output = _format([_full_read_log()], is_session=True)
    assert "## Resource Contents" not in output


def test_failed_action_with_content_renders_in_resource_contents():
    failed_log = ActionLog(
        status=ActionStatus.FAILURE,
        action_type="CREATE",
        params={"File Path": "docs/spec.md"},
        details={"error": "boom", "content": CONTENT},
    )
    output = _format([failed_log], is_session=False)
    assert output.count(SENTINEL) == 1
    assert "## Resource Contents" in output
