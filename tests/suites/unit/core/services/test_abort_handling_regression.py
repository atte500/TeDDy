import pytest
from datetime import datetime
from unittest.mock import MagicMock
from teddy_executor.core.domain.models import RunStatus, ExecutionReport, RunSummary
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.services.session_replanner import SessionReplanner
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator


@pytest.fixture
def orchestrator(  # noqa: PLR0913
    mock_run_plan,
    mock_session_manager,
    mock_fs,
    mock_plan_validator,
    mock_plan_parser,
    mock_user_interactor,
    mock_planning_service,
):
    replanner = SessionReplanner(
        file_system_manager=mock_fs,
        planning_service=mock_planning_service,
    )

    orchestrator_instance = SessionOrchestrator(
        execution_orchestrator=mock_run_plan,
        session_service=mock_session_manager,
        file_system_manager=mock_fs,
        plan_validator=mock_plan_validator,
        plan_parser=mock_plan_parser,
        user_interactor=mock_user_interactor,
        lifecycle_manager=MagicMock(),
        replanner=replanner,
    )
    return orchestrator_instance


def create_abort_report(user_request="Original"):
    summary = RunSummary(
        status=RunStatus.ABORTED, start_time=datetime.now(), end_time=datetime.now()
    )
    return ExecutionReport(
        run_summary=summary,
        user_request=user_request,
        metadata={},
        action_logs=[],
        original_actions=[],
    )


@pytest.mark.anyio
async def test_abort_always_prompts_and_guards_finalize(  # noqa: PLR0913
    orchestrator,
    mock_user_interactor,
    mock_fs,
    mock_run_plan,
    mock_plan_parser,
    mock_plan_validator,
):
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "### Plan\nRationale"

    mock_plan = MagicMock(spec=Plan)
    mock_plan.metadata = {}
    mock_plan_parser.parse.return_value = mock_plan
    mock_plan_validator.validate.return_value = []

    report = create_abort_report(user_request="Original Message (Should be ignored)")
    mock_run_plan.execute.return_value = report
    mock_user_interactor.ask_question.return_value = ""

    result = orchestrator.execute(plan_path="session/turn1/plan.md", message="Start")

    mock_user_interactor.ask_question.assert_called_once()
    assert result is None
    orchestrator._lifecycle_manager.finalize_turn.assert_not_called()


@pytest.mark.anyio
async def test_abort_with_new_message_continues_session(  # noqa: PLR0913
    orchestrator,
    mock_user_interactor,
    mock_fs,
    mock_run_plan,
    mock_plan_parser,
    mock_plan_validator,
):
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "### Plan\nRationale"

    mock_plan = MagicMock(spec=Plan)
    mock_plan.metadata = {}
    mock_plan_parser.parse.return_value = mock_plan
    mock_plan_validator.validate.return_value = []

    report = create_abort_report(user_request="Original")
    mock_run_plan.execute.return_value = report

    mock_user_interactor.ask_question.return_value = "Try something else"

    result = orchestrator.execute(plan_path="session/turn1/plan.md")

    assert result is not None
    assert result.user_request == "Try something else"
    assert mock_plan.metadata["user_request"] == "Try something else"
    orchestrator._lifecycle_manager.finalize_turn.assert_called_once()
