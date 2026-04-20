import pytest
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.session_manager import ISessionManager


@pytest.mark.anyio
async def test_run_plan_use_case_has_async_counterparts(container):
    """
    Acceptance: IRunPlanUseCase MUST expose async methods for non-blocking orchestration.
    """
    orchestrator = container.resolve(IRunPlanUseCase)

    # Assert the frontier: Methods should be defined but not yet implemented
    with pytest.raises(NotImplementedError):
        await orchestrator.async_execute(
            plan_content="# Plan\n- **Agent:** pathfinder\n- **Status:** SUCCESS\n"
        )

    with pytest.raises(NotImplementedError):
        await orchestrator.async_resume(session_name="test-session")


@pytest.mark.anyio
async def test_session_manager_has_async_counterparts(container):
    """
    Acceptance: ISessionManager MUST expose async methods for non-blocking turn transitions.
    """
    session_manager = container.resolve(ISessionManager)

    # Assert the frontier
    with pytest.raises(NotImplementedError):
        await session_manager.async_transition_to_next_turn(plan_path="test/plan.md")
