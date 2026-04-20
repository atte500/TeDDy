import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.domain.models import ExecutionReport, Plan
from teddy_executor.core.domain.models.execution_report import RunSummary, RunStatus
from teddy_executor.core.ports.outbound.session_manager import SessionState


@pytest.fixture
def orchestrator_deps():
    return {
        "execution_orchestrator": MagicMock(),
        "session_service": MagicMock(),
        "file_system_manager": MagicMock(),
        "report_formatter": MagicMock(),
        "plan_validator": MagicMock(),
        "planning_service": MagicMock(),
        "plan_parser": MagicMock(),
        "user_interactor": MagicMock(),
        "replanner": MagicMock(),
        "session_planner": MagicMock(),
    }


@pytest.fixture
def orchestrator(orchestrator_deps):
    return SessionOrchestrator(**orchestrator_deps)


@pytest.mark.anyio
async def test_async_execute_calls_execution_orchestrator(
    orchestrator, orchestrator_deps
):
    # Setup
    # Provide a dummy action to satisfy the domain model invariant
    plan = Plan(title="Test Plan", rationale="Test", actions=[{"type": "EXECUTE"}])

    summary = RunSummary(
        status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
    )
    report = ExecutionReport(
        run_summary=summary, plan_title="Test Plan", rationale="Test", action_logs=[]
    )

    # Mock dependencies
    orchestrator_deps["execution_orchestrator"].async_execute = AsyncMock(
        return_value=report
    )
    orchestrator_deps["plan_validator"].validate.return_value = []
    orchestrator_deps[
        "file_system_manager"
    ].path_exists.return_value = False  # Not session mode

    # Act
    result = await orchestrator.async_execute(plan=plan)

    # Assert
    assert result == report
    orchestrator_deps["execution_orchestrator"].async_execute.assert_called_once_with(
        plan=plan, plan_content=None, plan_path=None, interactive=True, message=None
    )


@pytest.mark.anyio
async def test_async_resume_pending_plan_calls_async_execute(
    orchestrator, orchestrator_deps
):
    # Setup
    session_name = "test-session"
    turn_path = "sessions/test-session/01"
    plan_path = f"{turn_path}/plan.md"

    summary = RunSummary(
        status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
    )
    report = ExecutionReport(run_summary=summary, plan_title="Test Plan")

    # Mock dependencies
    orchestrator_deps["session_service"].get_session_state.return_value = (
        SessionState.PENDING_PLAN,
        turn_path,
    )
    orchestrator_deps[
        "file_system_manager"
    ].path_exists.return_value = True  # For session mode detection inside execute
    orchestrator_deps["execution_orchestrator"].async_execute = AsyncMock(
        return_value=report
    )
    orchestrator_deps["plan_validator"].validate.return_value = []

    # Act
    result = await orchestrator.async_resume(session_name=session_name)

    # Assert
    assert result == report
    orchestrator_deps["execution_orchestrator"].async_execute.assert_called_once()
    assert (
        orchestrator_deps["execution_orchestrator"].async_execute.call_args.kwargs[
            "plan_path"
        ]
        == plan_path
    )


@pytest.mark.anyio
async def test_async_resume_empty_calls_planning_then_execute(
    orchestrator, orchestrator_deps
):
    # Setup
    session_name = "test-session"
    turn_path = "sessions/test-session/01"

    summary = RunSummary(
        status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
    )
    report = ExecutionReport(run_summary=summary, plan_title="Planned")
    plan = Plan(title="Planned", rationale="Test", actions=[{"type": "EXECUTE"}])

    # Mock dependencies
    orchestrator_deps["session_service"].get_session_state.return_value = (
        SessionState.EMPTY,
        turn_path,
    )
    # Mock SessionPlanner (the service that orchestrates the prompt + PlanningService)
    orchestrator_deps["session_planner"].async_trigger_new_plan = AsyncMock(
        return_value=session_name
    )
    orchestrator_deps["execution_orchestrator"].async_execute = AsyncMock(
        return_value=report
    )
    orchestrator_deps["file_system_manager"].path_exists.return_value = True
    orchestrator_deps["file_system_manager"].read_file.return_value = "raw-content"
    orchestrator_deps["plan_parser"].parse.return_value = plan
    orchestrator_deps["plan_validator"].validate.return_value = []

    # Act
    result = await orchestrator.async_resume(session_name=session_name)

    # Assert
    assert result == report
    orchestrator_deps["session_planner"].async_trigger_new_plan.assert_called_once_with(
        turn_path, message=None
    )
    orchestrator_deps["execution_orchestrator"].async_execute.assert_called_once()
