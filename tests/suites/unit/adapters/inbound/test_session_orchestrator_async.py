import pytest
from unittest.mock import AsyncMock
from datetime import datetime
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.domain.models import ExecutionReport, Plan
from teddy_executor.core.domain.models.execution_report import RunSummary, RunStatus
from teddy_executor.core.ports.outbound.session_manager import (
    ISessionManager,
)
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.ports.outbound import (
    IFileSystemManager,
    IUserInteractor,
)
from teddy_executor.core.services.session_replanner import SessionReplanner
from tests.harness.setup.mocking import UnifiedMock


@pytest.fixture
def orchestrator_deps():
    from teddy_executor.core.services.session_lifecycle_manager import (
        SessionLifecycleManager,
    )

    return {
        "execution_orchestrator": UnifiedMock(spec=IRunPlanUseCase),
        "session_service": UnifiedMock(spec=ISessionManager),
        "file_system_manager": UnifiedMock(spec=IFileSystemManager),
        "plan_validator": UnifiedMock(spec=IPlanValidator),
        "plan_parser": UnifiedMock(spec=IPlanParser),
        "user_interactor": UnifiedMock(spec=IUserInteractor),
        "lifecycle_manager": UnifiedMock(spec=SessionLifecycleManager),
        "replanner": UnifiedMock(spec=SessionReplanner),
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
async def test_async_resume_delegates_to_lifecycle_manager(
    orchestrator, orchestrator_deps
):
    # Setup
    session_name = "test-session"
    summary = RunSummary(
        status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
    )
    report = ExecutionReport(run_summary=summary, plan_title="Test Plan")

    orchestrator_deps["lifecycle_manager"].async_resume.return_value = report

    # Act
    result = await orchestrator.async_resume(session_name=session_name)

    # Assert
    assert result == report
    orchestrator_deps["lifecycle_manager"].async_resume.assert_called_once_with(
        session_name, orchestrator, True, None
    )


@pytest.mark.anyio
async def test_async_execute_finalizes_turn_in_session_mode(
    orchestrator, orchestrator_deps
):
    # Setup
    plan = Plan(title="Test Plan", rationale="Test", actions=[{"type": "EXECUTE"}])
    report = ExecutionReport(
        run_summary=RunSummary(
            status=RunStatus.SUCCESS, start_time=datetime.now(), end_time=datetime.now()
        ),
        plan_title="Test Plan",
    )

    plan_path = "session/01/plan.md"
    orchestrator_deps[
        "file_system_manager"
    ].path_exists.return_value = True  # session mode
    orchestrator_deps["execution_orchestrator"].async_execute.return_value = report
    orchestrator_deps["plan_validator"].validate.return_value = []

    # Act
    await orchestrator.async_execute(plan=plan, plan_path=plan_path)

    # Assert
    orchestrator_deps["lifecycle_manager"].async_finalize_turn.assert_called_once_with(
        plan_path, report
    )
