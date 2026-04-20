import pytest
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.session_manager import ISessionManager


@pytest.mark.anyio
async def test_run_plan_use_case_has_async_counterparts(container):
    """
    Acceptance: IRunPlanUseCase MUST expose async methods for non-blocking orchestration.
    """
    orchestrator = container.resolve(IRunPlanUseCase)

    # Assert the frontier: SessionOrchestrator is implemented, but ExecutionOrchestrator is not.
    # We provide a valid plan to pass the parser/validator in SessionOrchestrator.
    valid_plan = """# Plan: Test
- **Agent:** pathfinder
- **Status:** SUCCESS

## Rationale
~~~~~~
Test
~~~~~~

## Action Plan
### `EXECUTE`
- **Description:** Test
~~~~~~shell
echo 1
~~~~~~
"""
    with pytest.raises(
        NotImplementedError, match="Async execution not yet implemented."
    ):
        await orchestrator.async_execute(plan_content=valid_plan)

    # We create the session so async_resume can resolve the state and hit the next frontier
    session_manager = container.resolve(ISessionManager)
    session_path = session_manager.create_session("test-session", "pathfinder")
    actual_session_name = session_path.split("/")[-1]

    with pytest.raises(NotImplementedError):
        await orchestrator.async_resume(session_name=actual_session_name)


@pytest.mark.anyio
async def test_session_manager_has_async_counterparts(container):
    """
    Acceptance: ISessionManager MUST expose async methods for non-blocking turn transitions.
    """
    session_manager = container.resolve(ISessionManager)

    # Assert the frontier
    with pytest.raises(NotImplementedError):
        await session_manager.async_transition_to_next_turn(plan_path="test/plan.md")
