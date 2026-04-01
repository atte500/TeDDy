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

    app = ReviewerApp(plan=plan, system_env=system_env, console_tooling=console_tooling)

    # Act & Assert
    async with app.run_test() as pilot:
        # Check for the left pane (ActionTree)
        try:
            left_pane = app.query_one("#left-pane")
            assert isinstance(left_pane, Tree)
        except Exception:
            pytest.fail("ReviewerApp missing #left-pane (ActionTree)")

        # Check for the right pane (ParameterList)
        try:
            right_pane = app.query_one("#right-pane")
            assert isinstance(right_pane, Tree)
        except Exception:
            pytest.fail("ReviewerApp missing #right-pane (ParameterList)")

        # Simulate highlighting the first action
        left_pane = app.query_one("#left-pane")
        await pilot.press("down")
        await pilot.wait_for_scheduled_animations()

        # Verify right pane root label updated
        assert str(right_pane.root.label) == "Parameters for EXECUTE"

        # Verify right pane contains parameter leaf
        # We expect at least "command: ls" based on our Arrange block
        leaf_labels = [str(node.label) for node in right_pane.root.children]
        assert any("command: ls" in label for label in leaf_labels)
