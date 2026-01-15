from dataclasses import is_dataclass
from datetime import datetime
from unittest.mock import Mock

from teddy_executor.core.domain.models.execution_report import (
    V2_ActionLog,
    V2_ExecutionReport,
    V2_RunSummary,
)


def test_action_log_is_a_dataclass():
    """
    Tests that ActionLog is a dataclass.
    """
    assert is_dataclass(V2_ActionLog)


def test_action_log_creation():
    """
    Tests the creation of an ActionLog instance with valid data.
    """
    log = V2_ActionLog(
        status="SUCCESS",
        action_type="create_file",
        params={"path": "/tmp/test.txt"},
        details="File created successfully.",
    )
    assert log.status == "SUCCESS"
    assert log.action_type == "create_file"
    assert log.params == {"path": "/tmp/test.txt"}
    assert log.details == "File created successfully."


def test_execution_report_is_a_dataclass():
    """
    Tests that ExecutionReport is a dataclass.
    """
    assert is_dataclass(V2_ExecutionReport)


def test_execution_report_creation():
    """
    Tests the creation of an ExecutionReport instance.
    """
    # Using Mock for RunSummary as it's not implemented yet
    mock_summary = Mock()
    log1 = V2_ActionLog(status="SUCCESS", action_type="create_file", params={})
    log2 = V2_ActionLog(status="FAILURE", action_type="edit_file", params={})

    report = V2_ExecutionReport(run_summary=mock_summary, action_logs=[log1, log2])

    assert report.run_summary is mock_summary
    assert len(report.action_logs) == 2
    assert report.action_logs[0] is log1
    assert report.action_logs[1] is log2


def test_execution_report_defaults_to_empty_action_logs():
    """
    Tests that ExecutionReport defaults to an empty list of action logs.
    """
    mock_summary = Mock()
    report = V2_ExecutionReport(run_summary=mock_summary)
    assert report.action_logs == []


def test_run_summary_is_a_dataclass():
    """
    Tests that RunSummary is a dataclass.
    """
    assert is_dataclass(V2_RunSummary)


def test_run_summary_creation():
    """
    Tests the creation of a RunSummary instance.
    """
    # Using Mock for TeddyProject as it's not defined yet
    mock_project = Mock()
    start_time = datetime.now()
    end_time = datetime.now()

    summary = V2_RunSummary(
        status="SUCCESS",
        start_time=start_time,
        end_time=end_time,
        project=mock_project,
        error=None,
    )

    assert summary.status == "SUCCESS"
    assert summary.start_time is start_time
    assert summary.end_time is end_time
    assert summary.project is mock_project
    assert summary.error is None
