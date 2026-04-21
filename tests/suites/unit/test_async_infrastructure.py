import pytest
import anyio


@pytest.mark.anyio
async def test_anyio_infrastructure_is_functional():
    # Verify we can run a simple async operation
    result = await anyio.to_thread.run_sync(lambda: True)
    assert result is True


@pytest.mark.anyio
async def test_llm_client_mock_has_async_completion(mock_llm_client):
    """Verify that the global ILlmClient mock supports async_get_completion."""
    # This should fail if mock_llm_client.async_get_completion is a standard Mock
    # because standard Mocks are not awaitable.
    result = await mock_llm_client.async_get_completion([])
    # Verify we got real data from the mock (configured in mocks.py)
    assert "Mock Plan" in result.choices[0].message.content


@pytest.mark.anyio
async def test_planning_service_mock_is_async(mock_planning_service):
    """Verify that the global IPlanningUseCase mock supports async_generate_plan."""
    mock_planning_service.async_generate_plan.return_value = ("plan.md", 0.01)

    path, cost = await mock_planning_service.async_generate_plan("msg", "dir", [])
    assert path == "plan.md"


@pytest.mark.anyio
async def test_run_plan_mock_is_async(mock_run_plan):
    """Verify that the global IRunPlanUseCase mock supports async_execute."""
    from teddy_executor.core.domain.models.execution_report import (
        ExecutionReport,
        RunStatus,
        RunSummary,
    )
    from datetime import datetime
    from unittest.mock import AsyncMock

    # Diagnostic: Print the type of the async method
    print(f"\nDEBUG: async_execute type: {type(mock_run_plan.async_execute)}")
    assert isinstance(mock_run_plan.async_execute, AsyncMock)

    mock_summary = RunSummary(
        status=RunStatus.SUCCESS,
        start_time=datetime.now(),
        end_time=datetime.now(),
    )
    mock_report = ExecutionReport(run_summary=mock_summary)
    mock_run_plan.async_execute.return_value = mock_report

    report = await mock_run_plan.async_execute("plan.md")
    assert report.run_summary.status == RunStatus.SUCCESS


@pytest.mark.anyio
async def test_session_manager_mock_is_async(mock_session_manager):
    """Verify that the global ISessionManager mock supports async_transition_to_next_turn."""
    mock_session_manager.async_transition_to_next_turn.return_value = "02"

    result = await mock_session_manager.async_transition_to_next_turn(
        "01/plan.md", None
    )
    assert result == "02"
