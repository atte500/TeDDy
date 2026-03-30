import pytest
from unittest.mock import MagicMock
from textual.widgets import Tree
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


@pytest.mark.anyio
async def test_reviewer_app_filters_out_prune_in_manual_mode(container):
    """
    Verify that PRUNE actions are NOT added to the tree when is_session is False.
    """
    # Arrange
    action1 = ActionData(type="CREATE", params={"path": "new.py"})
    action2 = ActionData(type="PRUNE", params={"path": "old.py"})
    plan = Plan(
        title="Test Plan",
        rationale="Test",
        actions=[action1, action2],
        is_session=False,
    )

    app = ReviewerApp(
        plan=plan,
        system_env=container.resolve(ISystemEnvironment),
        console_tooling=MagicMock(),
    )

    # Act
    async with app.run_test():
        tree = app.query_one(Tree)

        # Assert
        # Root node has children. We expect only 1 child (CREATE), not 2.
        labels = [str(node.label) for node in tree.root.children]
        assert "[✓] CREATE: new.py" in labels
        assert any("PRUNE" in label for label in labels) is False


@pytest.mark.anyio
async def test_reviewer_app_shows_prune_in_session_mode(container):
    """
    Verify that PRUNE actions ARE added to the tree when is_session is True.
    """
    # Arrange
    action = ActionData(type="PRUNE", params={"path": "old.py"})
    plan = Plan(title="Test Plan", rationale="Test", actions=[action], is_session=True)

    app = ReviewerApp(
        plan=plan,
        system_env=container.resolve(ISystemEnvironment),
        console_tooling=MagicMock(),
    )

    # Act
    async with app.run_test():
        tree = app.query_one(Tree)

        # Assert
        labels = [str(node.label) for node in tree.root.children]
        assert any("PRUNE: old.py" in label for label in labels) is True
