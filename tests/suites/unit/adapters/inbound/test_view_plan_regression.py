import pytest
from unittest.mock import MagicMock, patch
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
    view_plan_handler,
)


@pytest.mark.anyio
async def test_view_plan_handler_uses_persistent_path_and_skips_confirm():
    # Setup
    mock_app = MagicMock()
    mock_app._file_system = MagicMock()
    mock_app._file_system.read_file.return_value = "Mocked Plan Content"

    plan_path = "some/real/path/plan.md"
    dummy_action = MagicMock(spec=ActionData)
    mock_app.plan = Plan(
        title="Test Plan",
        rationale="Rationale",
        actions=[dummy_action],
        plan_path=plan_path,
    )

    with patch(
        "teddy_executor.adapters.inbound.textual_plan_reviewer_previews.launch_editor"
    ) as mock_launch:
        mock_launch.return_value = None

        # Execute
        await view_plan_handler(mock_app)

        # Assert
        mock_launch.assert_called_once()
        _, kwargs = mock_launch.call_args
        assert kwargs.get("persistent_path") == plan_path
        assert kwargs.get("skip_confirm") is True
