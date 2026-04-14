import pytest
from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import ActionTree
from teddy_executor.core.domain.models.plan import Plan

from teddy_executor.core.domain.models.plan import ActionData


@pytest.mark.anyio
async def test_tui_section_navigation_keys(mock_env, mock_action_dispatcher):
    # Setup a minimal plan
    plan = Plan(
        title="Test Plan",
        rationale="### Why\nTo test navigation.\n\n1. First\nReasoning.",
        actions=[ActionData(type="READ", params={"resource": "README.md"})],
        metadata={"Status": "SUCCESS"},
    )

    # Use a dummy ConsoleToolingHelper
    from unittest.mock import MagicMock

    mock_console_tooling = MagicMock()

    app = ReviewerApp(
        plan=plan,
        system_env=mock_env,
        console_tooling=mock_console_tooling,
        action_dispatcher=mock_action_dispatcher,
    )

    async with app.run_test() as pilot:
        # Note: pilot is used below for .press()
        tree = app.query_one(ActionTree)

        # Verify initial focus on Rationale
        assert tree.cursor_node.data == ActionTree.RATIONALE_ROOT

        # Press Ctrl+Down to jump to Action Plan
        await pilot.press("ctrl+down")
        assert tree.cursor_node.data == ActionTree.ACTION_PLAN_ROOT

        # Press Alt+Up to jump back to Rationale
        await pilot.press("alt+up")
        assert tree.cursor_node.data == ActionTree.RATIONALE_ROOT

        # Press Shift+Down to jump to Action Plan
        await pilot.press("shift+down")
        assert tree.cursor_node.data == ActionTree.ACTION_PLAN_ROOT
