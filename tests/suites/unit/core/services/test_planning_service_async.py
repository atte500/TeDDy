import pytest
from teddy_executor.core.services.planning_service import PlanningService


@pytest.mark.anyio
async def test_planning_service_has_async_generate_plan_seam():
    # Setup: Create service with mocked dependencies
    from unittest.mock import AsyncMock, MagicMock

    mock_context = AsyncMock()
    # Context must have header and content attributes
    mock_context_result = MagicMock()
    mock_context_result.header = "Header"
    mock_context_result.content = "Content"
    mock_context.async_get_context.return_value = mock_context_result

    # LLM Client has both sync and async methods.
    # Use MagicMock and selectively assign AsyncMock to async methods.
    mock_llm = MagicMock()
    # Mocking the response to avoid structural validation errors
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[
        0
    ].message.content = "# Plan\n- **Agent:** pathfinder\n- **Status:** SUCCESS\n\n## Rationale\n~~~~~~\nTest\n~~~~~~\n\n## Action Plan\n### EXECUTE\n- Description: test\n~~~~~~shell\necho 1\n~~~~~~\n"
    mock_response.model = "test-model"

    mock_llm.async_get_completion = AsyncMock(return_value=mock_response)
    mock_llm.get_completion_cost.return_value = 0.01
    mock_llm.get_token_count.return_value = 100

    service = PlanningService(
        context_service=mock_context,
        llm_client=mock_llm,
        file_system_manager=MagicMock(),
        config_service=MagicMock(),
    )

    # Act: Execute the now-implemented method
    plan_path, cost = await service.async_generate_plan(
        user_message="test", turn_dir="test_dir"
    )

    # Assert: Method successfully generates a plan (proves implementation exists)
    assert plan_path is not None
    assert cost == 0.01
