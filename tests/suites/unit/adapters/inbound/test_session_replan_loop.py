from punq import Container
from datetime import datetime, timezone
from teddy_executor.core.domain.models.execution_report import (
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from unittest.mock import MagicMock
from teddy_executor.adapters.inbound.cli_helpers import handle_report_output
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor


class MockFormatter(IMarkdownReportFormatter):
    def format(self, report):
        return "Mock Report"


def test_handle_report_output_does_not_exit_in_session_mode():
    """
    VERIFIES FIX: Validation failures in session mode should not trigger typer.Exit,
    as they are handled by an automated re-plan loop.
    """
    container = Container()
    container.register(IMarkdownReportFormatter, MockFormatter)
    container.register(IUserInteractor, MagicMock())

    report = ExecutionReport(
        plan_title="Failing Plan",
        run_summary=RunSummary(
            status=RunStatus.VALIDATION_FAILED,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
    )

    # With the fix, we can now pass exit_on_failure=False.
    # This should return normally instead of raising click.exceptions.Exit.
    handle_report_output(
        container, report, no_copy=True, silent=True, exit_on_failure=False
    )
