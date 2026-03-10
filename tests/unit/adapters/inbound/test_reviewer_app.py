from contextlib import contextmanager
from unittest.mock import Mock
import pytest
from textual.widgets import Header, Footer, Tree
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp


@pytest.mark.anyio
async def test_reviewer_app_has_required_widgets():
    """
    Verify that ReviewerApp composes the required widgets.
    """
    # Arrange
    action = ActionData(type="READ", params={"resource": "foo.txt"})
    plan = Plan(title="Test Plan", rationale="Test Rationale", actions=[action])
    app = ReviewerApp(plan=plan, system_env=Mock(), file_system=Mock())

    # Act & Assert
    async with app.run_test():
        assert app.query_one(Header)
        assert app.query_one(Footer)
        assert app.query_one(Tree)


@pytest.mark.anyio
async def test_reviewer_app_populates_tree_with_actions():
    """
    Verify that ReviewerApp populates the tree with actions from the plan.
    """
    # Arrange
    actions = [
        ActionData(type="CREATE", params={"path": "src/foo.py"}),
        ActionData(type="READ", params={"resource": "docs/readme.md"}),
    ]
    plan = Plan(title="Test Plan", rationale="Test Rationale", actions=actions)
    app = ReviewerApp(plan=plan, system_env=Mock(), file_system=Mock())

    # Act & Assert
    async with app.run_test():
        tree = app.query_one(Tree)
        # Root node + 2 action nodes
        expected_node_count = 2
        assert len(tree.root.children) == expected_node_count
        assert "CREATE" in str(tree.root.children[0].label)
        assert "READ" in str(tree.root.children[1].label)


@pytest.mark.anyio
async def test_reviewer_app_toggles_action_selection():
    """
    Verify that ReviewerApp toggles action selection when Enter is pressed.
    """
    # Arrange
    action = ActionData(type="CREATE", params={"path": "src/foo.py"}, selected=True)
    plan = Plan(title="Test Plan", rationale="Test Rationale", actions=[action])
    app = ReviewerApp(plan=plan, system_env=Mock(), file_system=Mock())

    async with app.run_test() as pilot:
        tree = app.query_one(Tree)
        node = tree.root.children[0]

        # Verify initial state
        assert action.selected is True
        assert "[✓]" in str(node.label)

        # Act: Navigate to first child and press enter
        await pilot.press("down")
        await pilot.press("enter")

        # Assert: Selection toggled and label updated
        assert action.selected is False
        assert "[ ]" in str(node.label)

        # Act: Press enter again
        await pilot.press("enter")

        # Assert: Toggled back
        assert action.selected is True
        assert "[✓]" in str(node.label)


@pytest.mark.anyio
async def test_reviewer_app_submits_plan():
    """
    Verify that ReviewerApp exits and returns the plan when 's' is pressed.
    """
    # Arrange
    action = ActionData(type="CREATE", params={"path": "src/foo.py"}, selected=True)
    plan = Plan(title="Test Plan", rationale="Test Rationale", actions=[action])
    app = ReviewerApp(plan=plan, system_env=Mock(), file_system=Mock())

    async with app.run_test() as pilot:
        # Act: Press 's' to submit
        await pilot.press("s")

        # Assert: App returned the plan
        assert app.return_value == plan


@pytest.mark.anyio
async def test_reviewer_app_cancels_on_q():
    """
    Verify that ReviewerApp exits and returns None when 'q' is pressed.
    """
    # Arrange
    action = ActionData(type="CREATE", params={"path": "src/foo.py"}, selected=True)
    plan = Plan(title="Test Plan", rationale="Test Rationale", actions=[action])
    app = ReviewerApp(plan=plan, system_env=Mock(), file_system=Mock())

    async with app.run_test() as pilot:
        # Act: Press 'q' to cancel
        await pilot.press("q")

        # Assert: App returned None
        assert app.return_value is None


@pytest.mark.anyio
async def test_reviewer_app_previews_create_action(tmp_path):
    """
    Verify that ReviewerApp launches an editor for CREATE actions and updates content.
    """
    # Arrange
    initial_content = "old content"
    new_content = "new modified content"
    action = ActionData(
        type="CREATE", params={"path": "src/foo.py", "content": initial_content}
    )
    plan = Plan(title="Test Plan", rationale="Test Rationale", actions=[action])

    mock_system_env = Mock()
    temp_file = str(tmp_path / "temp_preview.py")
    mock_system_env.create_temp_file.return_value = temp_file
    mock_system_env.get_env.return_value = "nano"  # Mocking an editor

    def simulate_editor_edit(*args, **kwargs):
        with open(temp_file, "w") as f:
            f.write(new_content)

    mock_system_env.run_command.side_effect = simulate_editor_edit

    app = ReviewerApp(plan=plan, system_env=mock_system_env, file_system=Mock())

    # Patch suspend to be a no-op for headless testing
    @contextmanager
    def mock_suspend():
        yield

    app.suspend = mock_suspend

    async with app.run_test() as pilot:
        # Act: Navigate to action and press 'p'
        await pilot.press("down")
        await pilot.press("p")

        # Assert: Editor was launched with temp file
        mock_system_env.create_temp_file.assert_called_once_with(suffix=".py")
        mock_system_env.run_command.assert_called()

        # Assert: Action content was updated
        assert action.params["content"] == new_content
        # Assert: Label marked as modified (implied by design but let's check)
        tree = app.query_one(Tree)
        assert "*" in str(tree.root.children[0].label)


@pytest.mark.anyio
async def test_reviewer_app_previews_edit_action(tmp_path):
    """
    Verify that ReviewerApp launches an editor for EDIT actions with proposed state.
    """
    # Arrange
    initial_content = "line 1\nline 2"
    proposed_content = "line 1\nline 2 modified"
    user_content = "line 1\nline 2 modified by user"

    # Mocking the filesystem content for the EditSimulator which will be used by the app
    # (Actually we'll likely mock the EditSimulator or the IFileSystemManager in the App's context)
    action = ActionData(
        type="EDIT",
        params={
            "path": "src/foo.py",
            "edits": [{"find": "line 2", "replace": "line 2 modified"}],
        },
    )
    plan = Plan(title="Test Plan", rationale="Test Rationale", actions=[action])

    mock_system_env = Mock()
    temp_file = str(tmp_path / "temp_preview_edit.py")
    mock_system_env.create_temp_file.return_value = temp_file
    mock_system_env.get_env.return_value = "nano"

    # We also need to mock IFileSystemManager to provide the 'original' content
    mock_fs_manager = Mock()
    mock_fs_manager.read_file.return_value = initial_content

    def simulate_editor_edit(*args, **kwargs):
        # Verify the temp file was seeded with proposed content
        with open(temp_file, "r") as f:
            assert f.read() == proposed_content
        with open(temp_file, "w") as f:
            f.write(user_content)

    mock_system_env.run_command.side_effect = simulate_editor_edit

    # Injecting dependencies - we'll need to update ReviewerApp signature
    app = ReviewerApp(
        plan=plan, system_env=mock_system_env, file_system=mock_fs_manager
    )

    @contextmanager
    def mock_suspend():
        yield

    app.suspend = mock_suspend

    async with app.run_test() as pilot:
        await pilot.press("down")
        await pilot.press("p")

        # Assert: Action was converted to a CREATE-like simplified EDIT or parameters updated
        # Per spec: "Once confirmed, the tool calculates the final changes and updates the action."
        # To keep it simple, we'll assert that the action.params now contains the final content
        # or a simplified edit block.
        assert action.modified is True
        # For now, let's assume it updates 'content' parameter to signal a manual override
        assert action.params["content"] == user_content


@pytest.mark.anyio
async def test_reviewer_app_toggles_all_actions():
    """
    Verify that ReviewerApp toggles all actions correctly when 'a' is pressed.
    """
    # Arrange: 1 selected, 1 unselected
    actions = [
        ActionData(type="CREATE", params={"path": "src/foo.py"}, selected=True),
        ActionData(type="READ", params={"resource": "docs/readme.md"}, selected=False),
    ]
    plan = Plan(title="Test Plan", rationale="Test Rationale", actions=actions)
    app = ReviewerApp(plan=plan, system_env=Mock(), file_system=Mock())

    async with app.run_test() as pilot:
        tree = app.query_one(Tree)

        # Act: Press 'a' (Should select all because one is unselected)
        await pilot.press("a")
        assert all(a.selected for a in actions)
        assert "[✓]" in str(tree.root.children[0].label)
        assert "[✓]" in str(tree.root.children[1].label)

        # Act: Press 'a' again (Should unselect all because all are selected)
        await pilot.press("a")
        assert all(not a.selected for a in actions)
        assert "[ ]" in str(tree.root.children[0].label)
        assert "[ ]" in str(tree.root.children[1].label)


def test_reviewer_app_initialization():
    """
    Verify that ReviewerApp can be initialized with a plan and system env.
    """
    # Arrange
    action = ActionData(type="READ", params={"resource": "foo.txt"})
    plan = Plan(title="Test", rationale="Test", actions=[action])
    mock_system_env = Mock()

    # Act
    app = ReviewerApp(plan=plan, system_env=mock_system_env, file_system=Mock())

    # Assert
    assert app.plan == plan
    assert app._system_env == mock_system_env
