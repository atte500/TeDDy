import pytest
from textual.widgets import Header, Footer, Tree
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


@pytest.mark.anyio
async def test_reviewer_app_has_required_widgets(container):
    action = ActionData(type="READ", params={"resource": "foo.txt"})
    plan = Plan(title="Test Plan", rationale="Test Rationale", actions=[action])
    app = ReviewerApp(
        plan=plan,
        system_env=container.resolve(ISystemEnvironment),
        file_system=container.resolve(IFileSystemManager),
    )

    async with app.run_test():
        assert app.query_one(Header)
        assert app.query_one(Footer)
        assert app.query_one(Tree)


@pytest.mark.anyio
async def test_reviewer_app_populates_tree_with_actions(container):
    actions = [
        ActionData(type="CREATE", params={"path": "src/foo.py"}),
        ActionData(type="READ", params={"resource": "docs/readme.md"}),
    ]
    plan = Plan(title="Test Plan", rationale="Test Rationale", actions=actions)
    app = ReviewerApp(
        plan=plan,
        system_env=container.resolve(ISystemEnvironment),
        file_system=container.resolve(IFileSystemManager),
    )

    async with app.run_test():
        tree = app.query_one(Tree)
        expected_action_count = 2
        assert len(tree.root.children) == expected_action_count
        assert "CREATE" in str(tree.root.children[0].label)
        assert "READ" in str(tree.root.children[1].label)


@pytest.mark.anyio
async def test_reviewer_app_toggles_action_selection(container):
    action = ActionData(type="CREATE", params={"path": "src/foo.py"}, selected=True)
    plan = Plan(title="Test Plan", rationale="Test Rationale", actions=[action])
    app = ReviewerApp(
        plan=plan,
        system_env=container.resolve(ISystemEnvironment),
        file_system=container.resolve(IFileSystemManager),
    )

    async with app.run_test() as pilot:
        tree = app.query_one(Tree)
        node = tree.root.children[0]
        assert action.selected is True
        assert "[✓]" in str(node.label)

        await pilot.press("down", "enter")
        assert action.selected is False
        assert "[ ]" in str(node.label)

        await pilot.press("enter")
        assert action.selected is True
        assert "[✓]" in str(node.label)


@pytest.mark.anyio
async def test_reviewer_app_submits_plan(container):
    action = ActionData(type="CREATE", params={"path": "src/foo.py"}, selected=True)
    plan = Plan(title="Test Plan", rationale="Test Rationale", actions=[action])
    app = ReviewerApp(
        plan=plan,
        system_env=container.resolve(ISystemEnvironment),
        file_system=container.resolve(IFileSystemManager),
    )

    async with app.run_test() as pilot:
        await pilot.press("s")
        assert app.return_value == plan


@pytest.mark.anyio
async def test_reviewer_app_cancels_on_q(container):
    action = ActionData(type="CREATE", params={"path": "src/foo.py"}, selected=True)
    plan = Plan(title="Test Plan", rationale="Test Rationale", actions=[action])
    app = ReviewerApp(
        plan=plan,
        system_env=container.resolve(ISystemEnvironment),
        file_system=container.resolve(IFileSystemManager),
    )

    async with app.run_test() as pilot:
        await pilot.press("q")
        assert app.return_value is None


@pytest.mark.anyio
async def test_reviewer_app_toggles_all_actions(container):
    actions = [
        ActionData(type="CREATE", params={"path": "src/foo.py"}, selected=True),
        ActionData(type="READ", params={"resource": "docs/readme.md"}, selected=False),
    ]
    plan = Plan(title="Test Plan", rationale="Test Rationale", actions=actions)
    app = ReviewerApp(
        plan=plan,
        system_env=container.resolve(ISystemEnvironment),
        file_system=container.resolve(IFileSystemManager),
    )

    async with app.run_test() as pilot:
        tree = app.query_one(Tree)
        await pilot.press("a")
        assert all(a.selected for a in actions)
        assert "[✓]" in str(tree.root.children[0].label)
        assert "[✓]" in str(tree.root.children[1].label)

        await pilot.press("a")
        assert all(not a.selected for a in actions)
        assert "[ ]" in str(tree.root.children[0].label)
        assert "[ ]" in str(tree.root.children[1].label)


def test_reviewer_app_initialization(container):
    action = ActionData(type="READ", params={"resource": "foo.txt"})
    plan = Plan(title="Test", rationale="Test", actions=[action])
    mock_system_env = container.resolve(ISystemEnvironment)
    app = ReviewerApp(
        plan=plan,
        system_env=mock_system_env,
        file_system=container.resolve(IFileSystemManager),
    )
    assert app.plan == plan
    assert app._system_env == mock_system_env
