"""Unit tests for pipeline mode wiring in session_cli_handlers."""

from typing import List
from unittest.mock import Mock
from datetime import datetime

import pytest
import typer
from teddy_executor.core.domain.models.execution_report import (
    ActionLog,
    ActionStatus,
    ExecutionReport,
    RunSummary,
    RunStatus,
)


def _make_report(action_logs: List[ActionLog]) -> ExecutionReport:
    """Helper to create an ExecutionReport with given action_logs."""
    summary = RunSummary(
        status=RunStatus.SUCCESS,
        start_time=datetime(2025, 1, 1),
        end_time=datetime(2025, 1, 1),
    )
    return ExecutionReport(
        run_summary=summary,
        action_logs=action_logs,
        metadata={"cumulative_cost": "0.0"},
    )


def test_handle_new_session_pipeline_no_message_raises_exit(capsys) -> None:
    """When pipeline=True and no -m argument, handle_new_session must exit with code 1
    and display the correct error message."""
    from teddy_executor.adapters.inbound.session_cli_handlers import handle_new_session

    mock_interactor = Mock()
    mock_container = Mock()
    mock_container.resolve.return_value = mock_interactor

    with pytest.raises(typer.Exit):
        handle_new_session(
            container=mock_container,
            name="test_session",
            agent="assistant",
            interactive=False,
            no_copy=False,
            message=None,
            pipeline=True,
        )

    captured = capsys.readouterr()
    assert "Pipeline mode requires an initial message via -m/--message." in captured.err


def _build_mock_container_for_orchestrate() -> tuple[Mock, Mock]:
    """Build a mock container that resolves IRunPlanUseCase, ISessionManager, ISessionLoopGuard.
    Returns (mock_container, mock_orchestrator)."""

    mock_orchestrator = Mock()
    mock_session_manager = Mock()
    mock_loop_guard = Mock()

    # session_manager.get_latest_turn returns a fake path
    mock_session_manager.get_latest_turn.return_value = "01"
    mock_session_manager.get_cumulative_cost.return_value = 0.0

    # loop_guard.should_continue returns (True, None) to not break
    mock_loop_guard.should_continue.return_value = (True, None)

    def mock_resolve(iface, **kwargs):
        iface_name = iface.__name__ if hasattr(iface, "__name__") else str(iface)
        if "RunPlanUseCase" in iface_name:
            return mock_orchestrator
        elif "SessionManager" in iface_name:
            return mock_session_manager
        elif "SessionLoopGuard" in iface_name:
            return mock_loop_guard
        return Mock()

    mock_container = Mock()
    mock_container.resolve.side_effect = mock_resolve
    return mock_container, mock_orchestrator


def test_orchestrate_session_loop_pipeline_breaks_on_message(monkeypatch) -> None:
    """When pipeline=True and report contains MESSAGE action, loop breaks after one turn."""
    # Arrange
    from teddy_executor.adapters.inbound.session_cli_handlers import (
        _orchestrate_session_loop,
    )

    # Mock handle_report_output to do nothing
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.cli_helpers.handle_report_output",
        lambda *args, **kwargs: None,
    )

    mock_container, mock_orchestrator = _build_mock_container_for_orchestrate()

    # Make resume return a report with a MESSAGE action log
    msg_log = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="MESSAGE",
        params={},
        details="Hello from agent",
    )
    report = _make_report([msg_log])
    mock_orchestrator.resume.return_value = ("test_session", report)

    # Act
    _orchestrate_session_loop(
        container=mock_container,
        session_name="test_session",
        interactive=False,
        no_copy=False,
        pipeline=True,
    )

    # Assert: resume was called exactly once (loop breaks after first iteration)
    assert mock_orchestrator.resume.call_count == 1


def test_orchestrate_session_loop_pipeline_no_message_continues(monkeypatch) -> None:
    """When pipeline=True but report has no MESSAGE, loop continues (resume called multiple times)."""
    # Arrange
    from teddy_executor.adapters.inbound.session_cli_handlers import (
        _orchestrate_session_loop,
    )

    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.cli_helpers.handle_report_output",
        lambda *args, **kwargs: None,
    )

    mock_container, mock_orchestrator = _build_mock_container_for_orchestrate()

    # First resume returns non-MESSAGE report, second returns None report to break loop
    read_log = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="READ",
        params={},
        details="",
    )
    report1 = _make_report([read_log])
    # Second call returns tuple with None report to break loop naturally
    mock_orchestrator.resume.side_effect = [
        ("test_session", report1),
        ("test_session", None),
    ]

    # Act
    _orchestrate_session_loop(
        container=mock_container,
        session_name="test_session",
        interactive=False,
        no_copy=False,
        pipeline=True,
    )

    # Assert: resume was called twice (first turn processed, second call gets None and breaks)
    assert mock_orchestrator.resume.call_count == 2


def test_orchestrate_session_loop_non_pipeline_ignores_message(monkeypatch) -> None:
    """When pipeline=False, MESSAGE in report does NOT break loop."""
    # Arrange
    from teddy_executor.adapters.inbound.session_cli_handlers import (
        _orchestrate_session_loop,
    )

    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.cli_helpers.handle_report_output",
        lambda *args, **kwargs: None,
    )

    mock_container, mock_orchestrator = _build_mock_container_for_orchestrate()

    # resume returns report with MESSAGE, second call returns None report to break loop
    msg_log = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="MESSAGE",
        params={},
        details="Hello",
    )
    report1 = _make_report([msg_log])
    mock_orchestrator.resume.side_effect = [
        ("test_session", report1),
        ("test_session", None),
    ]

    # Act
    _orchestrate_session_loop(
        container=mock_container,
        session_name="test_session",
        interactive=False,
        no_copy=False,
        pipeline=False,  # Not pipeline mode
    )

    # Assert: resume called twice (MESSAGE was ignored, loop continued to second iteration)
    assert mock_orchestrator.resume.call_count == 2
