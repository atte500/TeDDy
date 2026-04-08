import pytest
from unittest.mock import MagicMock
from teddy_executor.core.domain.models.plan import Plan, ActionData
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.services.action_dispatcher import ActionDispatcher


@pytest.mark.anyio
async def test_tui_modifying_edit_action_content_succeeds(env, monkeypatch):
    """
    Regression test for ensuring that modifying an EDIT action's content
    in the TUI does not cause a TypeError on execution.
    """
    # Arrange
    file_to_edit = "test_file.txt"
    original_content = "Hello, world!"
    modified_content = "Hello, Teddy!"

    fs_manager = env.container.resolve(IFileSystemManager)
    # Register as singleton so Dispatcher uses the SAME mock for execution
    env.container.register(IFileSystemManager, instance=fs_manager)

    # If it's a mock, configure it
    if hasattr(fs_manager, "read_file"):
        fs_manager.read_file.return_value = original_content

        # Ensure write_file and edit_file update the read_file return value for verification
        def _update_content(path=None, content=None, **kwargs):
            # Handle dispatcher translation: domain 'path' -> infra 'file_path'
            edits = kwargs.get("edits", content)

            # For EDIT, we calculate the 'new' content from the edits.
            if isinstance(edits, list):  # It's edits
                new_c = edits[0]["replace"]
            else:
                new_c = edits
            setattr(fs_manager.read_file, "return_value", str(new_c))

        fs_manager.write_file.side_effect = _update_content
        fs_manager.edit_file.side_effect = _update_content

    fs_manager.write_file(file_to_edit, original_content)

    # Mock the external editor to return the modified content
    monkeypatch.setenv("TEDDY_TEST_MOCK_EDITOR_OUTPUT", modified_content)

    action = ActionData(
        type="EDIT",
        params={
            "path": file_to_edit,
            "edits": [{"find": "Hello, world!", "replace": "Hello, Teddy!"}],
        },
        selected=True,
    )
    plan = Plan(title="Test Edit", rationale="Test", actions=[action])
    dispatcher = env.container.resolve(ActionDispatcher)

    system_env = env.container.resolve(ISystemEnvironment)
    # Ensure create_temp_file returns a valid string path for open()
    system_env.create_temp_file.side_effect = lambda suffix=".txt": str(
        env.workspace / f"temp_file{suffix}"
    )

    console_tooling = MagicMock()
    # Disable diff viewer to use the standard editor path in tests
    console_tooling.get_diff_viewer_command.return_value = None

    app = ReviewerApp(
        plan=plan,
        system_env=system_env,
        console_tooling=console_tooling,
        action_dispatcher=dispatcher,
        file_system=fs_manager,
    )

    # Act
    async with app.run_test() as pilot:
        await pilot.press("down")  # Highlight the action
        await pilot.press("e")  # Trigger edit/preview
        await pilot.wait_for_scheduled_animations()
        # Confirm the changes by pressing 'y' as per ConfirmScreen.on_key
        await pilot.press("y")
        await pilot.wait_for_scheduled_animations()

        # Assert that the action is marked as modified
        assert action.modified is True

        # Now, exit the TUI
        await pilot.press("ctrl+g")  # Approve and exit
        await pilot.wait_for_scheduled_animations()

    # Assert: Now execute the modified action via the dispatcher.
    # This is where the TypeError would occur if the bug were still present.
    dispatcher.dispatch_and_execute(action)

    # Verify the content was actually updated on disk
    final_content = fs_manager.read_file(file_to_edit)
    assert final_content == modified_content
