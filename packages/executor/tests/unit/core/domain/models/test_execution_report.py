from datetime import datetime

from teddy_executor.core.domain.models import (
    ActionLog,
    ExecutionReport,
    RunSummary,
    TeddyProject,
    ActionStatus,
    RunStatus,
)


def test_run_summary_creation():
    """Test that RunSummary can be created with valid enum status."""
    summary = RunSummary(
        status=RunStatus.SUCCESS,
        start_time=datetime.now(),
        end_time=datetime.now(),
        project=TeddyProject(name="test"),
    )
    assert summary.status == RunStatus.SUCCESS
    assert summary.status == "SUCCESS"  # Should also be comparable to string


def test_action_log_creation():
    """Test that ActionLog can be created with valid enum status."""
    log = ActionLog(
        status=ActionStatus.SKIPPED,
        action_type="test_action",
        params={"a": 1},
        details="skipped",
    )
    assert log.status == ActionStatus.SKIPPED
    assert log.status == "SKIPPED"


def test_execution_report_creation():
    """Test that a full ExecutionReport can be composed."""
    summary = RunSummary(
        status=RunStatus.FAILURE,
        start_time=datetime.now(),
        end_time=datetime.now(),
        project=TeddyProject(),
    )
    log = ActionLog(
        status=ActionStatus.FAILURE, action_type="test", params={}, details="error"
    )
    report = ExecutionReport(run_summary=summary, action_logs=[log])

    assert report.run_summary.status == RunStatus.FAILURE
    assert len(report.action_logs) == 1
    assert report.action_logs[0].status == ActionStatus.FAILURE
