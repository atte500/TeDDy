"""Unit tests: `## User Request` template placement consistency.

The locked consumption design (user-approved): the conditional
`## User Request` section in `execution_report.md.j2` must render at the
END of the report (after the Action Log) so template-rendered and
`_append_user_request`-appended sections share one placement (the append
path lands the section at end-of-file). The conditional render is
RETAINED - no always-render - protecting `session_service`'s
`^## User Request` prune-preservation detection (a position-independent
line scan).
"""

from datetime import datetime

import punq

from teddy_executor.core.domain.models.execution_report import (
    ActionLog,
    ActionStatus,
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)

REQUEST = "Follow-up request from the operator"


def _report(user_request: str | None) -> ExecutionReport:
    return ExecutionReport(
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime(2026, 10, 2, 12, 0, 0),
            end_time=datetime(2026, 10, 2, 12, 0, 0),
        ),
        plan_title="Follow-up Turn",
        action_logs=[
            ActionLog(
                status=ActionStatus.SUCCESS,
                action_type="EXECUTE",
                params={"command": "echo 1"},
                details="ok",
            )
        ],
        user_request=user_request,
    )


def _format(container: punq.Container, user_request: str | None) -> str:
    formatter = container.resolve(IMarkdownReportFormatter)
    return formatter.format(_report(user_request))


class TestUserRequestTemplatePlacement:
    """The template renders the User Request section at the END."""

    def test_user_request_renders_after_action_log(self, container) -> None:
        # Act
        output = _format(container, REQUEST)

        # Assert: the Action Log section precedes the User Request section.
        assert output.index("## Action Log") < output.index("## User Request")

    def test_user_request_renders_at_end_of_report(self, container) -> None:
        # Act
        output = _format(container, REQUEST)

        # Assert: the smart-fenced User Request block is the FINAL content
        # of the report - matching the `_append_user_request` end-of-file
        # placement so both paths share one position.
        assert output.rstrip().endswith("```")

    def test_user_request_section_absent_without_request(self, container) -> None:
        # Act
        output = _format(container, None)

        # Assert: the conditional render is retained (no always-render) -
        # the prune-preservation detection semantics stay intact.
        assert "## User Request" not in output
