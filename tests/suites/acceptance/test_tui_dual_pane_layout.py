import pytest
from unittest.mock import MagicMock
from textual.widgets import Tree
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.domain.models.plan import Plan, ActionData


@pytest.mark.anyio
async def test_reviewer_app_has_dual_pane_layout():
    """
    Verify that the ReviewerApp contains both an ActionTree and a ParameterList
    arranged in a horizontal layout.
    """
    # Arrange
    action = ActionData(type="EXECUTE", params={"command": "ls"})
    plan = Plan(
        title="Test Plan",
        rationale="Test",
        actions=[action],
        metadata={"Status": "Green 🟢"},
    )
    system_env = MagicMock()
    console_tooling = MagicMock()

    app = ReviewerApp(
        plan=plan,
        system_env=system_env,
        console_tooling=console_tooling,
        action_dispatcher=MagicMock(),
    )

    from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
        ParameterDetail,
    )

    # Act & Assert
    async with app.run_test() as pilot:
        # Check for the left pane (ActionTree)
        try:
            left_pane = app.query_one("#left-pane")
            assert isinstance(left_pane, Tree)
        except Exception:
            pytest.fail("ReviewerApp missing #left-pane (ActionTree)")

        # Check for the right pane (ParameterDetail)
        try:
            right_pane = app.query_one("#right-pane")
            assert isinstance(right_pane, ParameterDetail)
        except Exception:
            pytest.fail("ReviewerApp missing #right-pane (ParameterDetail)")

        # Simulate highlighting the first action
        await pilot.press("down")
        await pilot.wait_for_scheduled_animations()

        # Verify right pane (ParameterDetail) is updated with resolved parameters
        # EXECUTE type should have 4 parameters (command, allow_failure, background, timeout)
        # 'description' is hidden from the detail view to reduce clutter.
        expected_param_count = 4
        assert len(right_pane.children) == expected_param_count
