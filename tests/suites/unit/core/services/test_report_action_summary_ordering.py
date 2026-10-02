"""Regression: scalar action-summary metadata renders directly under Status.

Bug 55 (5b): the shared action-details macro was invoked at the END of every
action block, so scalar, status-adjacent metadata (`- **Details:**`,
`- **Return Code:**`) rendered AFTER the action-specific fields such as
`- **Command:**`. The fix splits the macro so scalar summary metadata is
emitted directly after `- **Status:**`, while multi-line diagnostic blocks
(`#### stdout`, `#### stderr`, `#### diff`) remain at block end.
"""

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
from tests.harness.observers.report_parser import ReportParser

TS = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)


def _format(*logs: ActionLog) -> str:
    report = ExecutionReport(
        plan_title="Action Summary Ordering",
        run_summary=RunSummary(status=RunStatus.SUCCESS, start_time=TS, end_time=TS),
        action_logs=list(logs),
    )
    return MarkdownReportFormatter().format(report)


def test_string_details_render_between_status_and_command() -> None:
    """A scalar `- **Details:**` line sits directly after `- **Status:**`."""
    output = _format(
        ActionLog(
            status=ActionStatus.SUCCESS,
            action_type="EXECUTE",
            params={"command": "ls -la", "expected_outcome": "list files"},
            details="User deselected this action in the plan reviewer.",
        )
    )

    status_i = output.index("- **Status:**")
    details_i = output.index("- **Details:**")
    command_i = output.index("- **Command:**")
    assert status_i < details_i < command_i


def test_return_code_hoists_while_output_blocks_stay_after_command() -> None:
    """Scalar `- **Return Code:**` hoists; stdout/stderr stay at block end."""
    output = _format(
        ActionLog(
            status=ActionStatus.FAILURE,
            action_type="EXECUTE",
            params={"command": "false", "expected_outcome": "fail"},
            details={"stdout": "out-line", "stderr": "err-line", "return_code": 1},
        )
    )

    status_i = output.index("- **Status:**")
    return_code_i = output.index("- **Return Code:**")
    command_i = output.index("- **Command:**")
    stdout_i = output.index("#### `stdout`")
    stderr_i = output.index("#### `stderr`")

    assert status_i < return_code_i < command_i
    assert command_i < stdout_i < stderr_i


def test_parser_still_resolves_details_after_reorder() -> None:
    """The ReportParser is order-independent: return_code/stdout/stderr survive."""
    output = _format(
        ActionLog(
            status=ActionStatus.FAILURE,
            action_type="EXECUTE",
            params={"command": "bad"},
            details={"stdout": "out", "stderr": "err", "return_code": 42},
        )
    )

    parser = ReportParser(output)
    assert parser.action_logs[0].details["return_code"] == 42
    assert parser.action_logs[0].details["stdout"] == "out"
    assert parser.action_logs[0].details["stderr"] == "err"
