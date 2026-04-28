import pytest
from unittest.mock import MagicMock
from datetime import datetime
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.core.domain.models.execution_report import (
    ExecutionReport,
    RunSummary,
    RunStatus,
)
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator


@pytest.fixture
def session_orchestrator_setup():
    mock_exec = MagicMock()
    mock_session_service = MagicMock()
    mock_fs = MagicMock()
    mock_validator = MagicMock()
    mock_parser = MagicMock()
    mock_user = MagicMock()
    mock_lifecycle = MagicMock()
    mock_replanner = MagicMock()

    orchestrator = SessionOrchestrator(
        mock_exec,
        mock_session_service,
        mock_fs,
        mock_validator,
        mock_parser,
        mock_user,
        mock_lifecycle,
        mock_replanner,
    )

    # Mock session mode
    mock_fs.path_exists.return_value = True
    mock_validator.validate.return_value = []

    return orchestrator, mock_exec, mock_user


def test_session_terminates_on_empty_abort_response(session_orchestrator_setup):
    """Bug 1 & 3: Session should terminate (return None) if abort prompt is empty."""
    orchestrator, mock_exec, mock_user = session_orchestrator_setup

    report = ExecutionReport(
        run_summary=RunSummary(
            status=RunStatus.ABORTED, start_time=datetime.now(), end_time=datetime.now()
        ),
        plan_title="Test",
    )
    mock_exec.execute.return_value = report
    mock_user.ask_question.return_value = ""

    plan = Plan(
        title="T", rationale="R", actions=[ActionData(type="PROMPT", params={})]
    )

    final_report = orchestrator.execute(plan=plan, plan_path="session/turn/plan.md")

    assert final_report is None


def test_session_respects_existing_message_on_abort(session_orchestrator_setup):
    """Bug 2: Session should not re-prompt if a message already exists in the report."""
    orchestrator, mock_exec, mock_user = session_orchestrator_setup

    report = ExecutionReport(
        run_summary=RunSummary(
            status=RunStatus.ABORTED, start_time=datetime.now(), end_time=datetime.now()
        ),
        plan_title="Test",
        user_request="Existing Message",
    )
    mock_exec.execute.return_value = report

    plan = Plan(
        title="T", rationale="R", actions=[ActionData(type="PROMPT", params={})]
    )

    final_report = orchestrator.execute(plan=plan, plan_path="session/turn/plan.md")

    assert final_report.user_request == "Existing Message"
    mock_user.ask_question.assert_not_called()


def test_execution_orchestrator_propagates_tui_message_on_abort():
    """Bug 2: ExecutionOrchestrator should pull user_request from plan metadata on abort."""
    mock_parser = MagicMock()
    mock_validator = MagicMock()
    mock_validator.validate.return_value = []
    mock_executor = MagicMock()
    mock_fs = MagicMock()
    mock_assembler = MagicMock()
    mock_reviewer = MagicMock()

    orchestrator = ExecutionOrchestrator(
        mock_parser,
        mock_validator,
        mock_executor,
        mock_fs,
        mock_assembler,
        mock_reviewer,
    )

    plan = Plan(
        title="T", rationale="R", actions=[ActionData(type="EXECUTE", params={})]
    )
    plan.metadata["user_request"] = "Captured in TUI"

    # Simulate TUI abort
    mock_reviewer.review.return_value = None

    def mock_assemble(_p, _logs, start, msg):
        return ExecutionReport(
            run_summary=RunSummary(
                status=RunStatus.SUCCESS, start_time=start, end_time=datetime.now()
            ),
            user_request=msg,
        )

    mock_assembler.assemble.side_effect = mock_assemble

    report = orchestrator.execute(plan=plan, interactive=True)

    assert report.run_summary.status == RunStatus.ABORTED
    assert report.user_request == "Captured in TUI"
