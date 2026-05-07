import pytest
from unittest.mock import MagicMock
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.core.domain.models.project_context import (
    ProjectContext,
    ContextItem,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


@pytest.mark.anyio
async def test_reviewer_app_toggles_context_item(env):
    # Arrange
    item = ContextItem(
        path="src/core.py",
        token_count=1000,
        git_status="M",
        scope="Session",
        selected=True,
    )
    context = ProjectContext(
        header="", content="", items=[item], agent_name="TestAgent"
    )
    plan = Plan(
        title="Test Plan",
        rationale="R",
        actions=[ActionData(type="READ", params={"path": "dummy"})],
    )

    app = ReviewerApp(
        plan=plan,
        project_context=context,
        system_env=env.get_service(ISystemEnvironment),
        console_tooling=MagicMock(),
        action_dispatcher=MagicMock(),
    )

    async with app.run_test() as pilot:
        from textual.widgets import Tree

        tree = pilot.app.query_one(Tree)

        # Ensure context root is expanded
        tree.cursor_node.expand()
        await pilot.pause()

        # Move cursor to the first context item (Context Root -> System -> Agent -> Session -> ITEM)
        await pilot.press("down", "down", "down", "down")
        await pilot.pause()

        # Debug: check where we are
        # print(f"DEBUG: Cursor at node {tree.cursor_node.label} with data {type(tree.cursor_node.data)}")

        # Act: Toggle selection (Space)
        await pilot.press("space")
        await pilot.pause()

    # Assert
    assert item.selected is False

    # Verify styling - check the markup string of the Rich Text label
    label_markup = getattr(
        tree.cursor_node.label, "markup", str(tree.cursor_node.label)
    )
    assert "strike" in label_markup or " s " in f" {label_markup} "
    assert "dim" in label_markup
    assert "src/core.py" in label_markup
