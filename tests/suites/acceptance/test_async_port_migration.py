import pytest
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.session_manager import (
    ISessionManager,
    SessionState,
)


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
    report = await orchestrator.async_execute(plan_content=valid_plan)
    assert report.run_summary.status == "SUCCESS"

    # We create the session so async_resume can resolve the state and hit the next frontier
    from teddy_executor.core.ports.inbound.init import IInitUseCase

    container.resolve(IInitUseCase).ensure_initialized()
    session_manager = container.resolve(ISessionManager)
    session_path = session_manager.create_session("test-session", "pathfinder")
    actual_session_name = session_path.split("/")[-1]

    # Mock user interaction and LLM to reach the frontier
    from unittest.mock import patch
    from tests.harness.setup.mocking import UnifiedMock

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
    mock_response = UnifiedMock()
    mock_response.choices = [UnifiedMock()]
    mock_response.choices[0].message.content = valid_plan
    mock_response.model = "gpt-4o"

    with (
        patch(
            "teddy_executor.adapters.outbound.console_interactor.ConsoleInteractorAdapter.async_ask_question",
            return_value="Test instructions",
        ),
        patch(
            "teddy_executor.adapters.outbound.litellm_adapter.LiteLLMAdapter.async_get_completion",
            return_value=mock_response,
        ),
    ):
        resume_report = await orchestrator.async_resume(
            session_name=actual_session_name
        )
        assert resume_report.run_summary.status == "SUCCESS"


@pytest.mark.anyio
async def test_session_manager_has_async_counterparts(container):
    """
    Acceptance: ISessionManager MUST expose async methods for non-blocking turn transitions.
    """
    # 1. Setup
    from teddy_executor.core.ports.inbound.init import IInitUseCase

    container.resolve(IInitUseCase).ensure_initialized()
    session_manager = container.resolve(ISessionManager)

    # 2. Verify async_create_session
    session_path = await session_manager.async_create_session(
        "async-test", "pathfinder"
    )
    assert "async-test" in session_path
    assert ".teddy/sessions" in session_path

    # 3. Verify async_get_session_state
    session_name = session_path.split("/")[-1]
    state, latest_turn = await session_manager.async_get_session_state(session_name)
    assert state == SessionState.EMPTY
    assert latest_turn.endswith("01")

    # 4. Verify async_transition_to_next_turn
    # We need a plan.md and meta.yaml to transition
    from teddy_executor.core.ports.outbound.file_system_manager import (
        IFileSystemManager,
    )

    fs = container.resolve(IFileSystemManager)
    plan_path = f"{latest_turn}/plan.md"
    fs.write_file(plan_path, "# Plan")

    next_turn = await session_manager.async_transition_to_next_turn(plan_path=plan_path)
    assert next_turn.endswith("02")

    # 5. Verify async_resolve_context_paths
    contexts = await session_manager.async_resolve_context_paths(plan_path)
    assert "Session" in contexts
    assert "Turn" in contexts
