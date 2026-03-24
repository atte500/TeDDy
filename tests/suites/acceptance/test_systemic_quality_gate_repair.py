from tests.harness.setup.test_environment import TestEnvironment


def test_formatter_missing_status_regression(tmp_path, monkeypatch):
    """
    Reproduces the issue where MarkdownReportFormatter produces an incomplete report.
    """
    from teddy_executor.core.ports.outbound import IMarkdownReportFormatter
    from teddy_executor.core.domain.models.execution_report import (
        ExecutionReport,
        RunSummary,
        RunStatus,
    )
    from datetime import datetime, timezone

    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()

    formatter = env.get_service(IMarkdownReportFormatter)

    report = ExecutionReport(
        plan_title="Regression Test Plan",
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
    )

    rendered = formatter.format(report)

    # In the broken state, "Overall Status: SUCCESS" is missing due to serialization issues
    assert (
        "Overall Status:** SUCCESS" in rendered
        or "Overall Status:** SUCCESS" in rendered.replace(" ", "")
    )
