import pytest
from unittest.mock import Mock
from teddy_executor.core.services.planning_service import PlanningService


@pytest.mark.anyio
async def test_planning_service_has_async_generate_plan_seam():
    # Setup: Create service with mocked dependencies
    service = PlanningService(
        context_service=Mock(),
        llm_client=Mock(),
        file_system_manager=Mock(),
        config_service=Mock(),
    )

    # Act & Assert the Frontier: Confirm the seam exists but is not implemented.
    with pytest.raises(
        NotImplementedError, match="async_generate_plan is not yet implemented."
    ):
        await service.async_generate_plan(user_message="test", turn_dir="test_dir")
