from contextlib import contextmanager
import pytest
from textual.widgets import Tree
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


@pytest.mark.anyio
async def test_reviewer_app_previews_create_action(tmp_path, mock_env, container):
    initial_content = "old content"
    new_content = "new modified content"
    action = ActionData(
        type="CREATE", params={"path": "src/foo.py", "content": initial_content}
    )
    plan = Plan(title="Test Plan", rationale="Test Rationale", actions=[action])

    temp_file = str(tmp_path / "temp_preview.py")
    mock_env.create_temp_file.return_value = temp_file
    mock_env.get_env.return_value = "nano"

    def simulate_editor_edit(*args, **kwargs):
        with open(temp_file, "w") as f:
            f.write(new_content)

    mock_env.run_command.side_effect = simulate_editor_edit
    app = ReviewerApp(
        plan=plan,
        system_env=mock_env,
        file_system=container.resolve(IFileSystemManager),
    )

    @contextmanager
    def mock_suspend():
        yield

    app.suspend = mock_suspend

    async with app.run_test() as pilot:
        await pilot.press("down", "p")
        mock_env.create_temp_file.assert_called_once_with(suffix=".py")
        assert action.params["content"] == new_content
        tree = app.query_one(Tree)
        assert "*" in str(tree.root.children[0].label)


@pytest.mark.anyio
async def test_reviewer_app_previews_edit_action(tmp_path, mock_env, mock_fs):
    initial_content = "line 1\nline 2"
    proposed_content = "line 1\nline 2 modified"
    user_content = "line 1\nline 2 modified by user"

    action = ActionData(
        type="EDIT",
        params={
            "path": "src/foo.py",
            "edits": [{"find": "line 2", "replace": "line 2 modified"}],
        },
    )
    plan = Plan(title="Test Plan", rationale="Test Rationale", actions=[action])

    temp_file = str(tmp_path / "temp_preview_edit.py")
    mock_env.create_temp_file.return_value = temp_file
    mock_env.get_env.return_value = "nano"
    mock_fs.read_file.return_value = initial_content

    def simulate_editor_edit(*args, **kwargs):
        with open(temp_file, "r") as f:
            assert f.read() == proposed_content
        with open(temp_file, "w") as f:
            f.write(user_content)

    mock_env.run_command.side_effect = simulate_editor_edit
    app = ReviewerApp(plan=plan, system_env=mock_env, file_system=mock_fs)

    @contextmanager
    def mock_suspend():
        yield

    app.suspend = mock_suspend

    async with app.run_test() as pilot:
        await pilot.press("down", "p")
        assert action.modified is True
        assert action.params["content"] == user_content
