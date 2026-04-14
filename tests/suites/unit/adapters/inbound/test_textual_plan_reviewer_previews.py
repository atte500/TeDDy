import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
    preview_create,
    preview_prompt,
)
from teddy_executor.core.domain.models.plan import ActionData


@pytest.mark.anyio
async def test_preview_prompt_updates_user_response():
    """Verify that preview_prompt updates the action's user_response without confirmation modal."""
    # Setup
    app = MagicMock()
    app.INSTRUCTION_MARKER = "<!-- marker -->"
    app.push_screen_wait = AsyncMock()

    node = MagicMock()
    action = ActionData(type="PROMPT", params={"message": "Is this correct?"})

    # Mock launch_editor to return a response
    with patch(
        "teddy_executor.adapters.inbound.textual_plan_reviewer_previews.launch_editor",
        AsyncMock(return_value="Yes, it is."),
    ):
        # Driver
        await preview_prompt(app, action, node)

        # Observer
        assert action.user_response == "Yes, it is."
        assert action.modified is True
        app.push_screen_wait.assert_not_called()
        app._refresh_node.assert_called_once_with(node)


@pytest.mark.anyio
async def test_preview_create_updates_content_only():
    """Verify that preview_create updates content without path or confirmation modals."""
    # Setup
    app = MagicMock()
    app.INSTRUCTION_MARKER = "<!-- marker -->"
    app.push_screen_wait = AsyncMock()

    node = MagicMock()
    action = ActionData(
        type="CREATE", params={"path": "src/old_path.py", "content": "old content"}
    )

    # Mock launch_editor
    with patch(
        "teddy_executor.adapters.inbound.textual_plan_reviewer_previews.launch_editor",
        AsyncMock(return_value="new content"),
    ):
        # Driver
        await preview_create(app, action, node)

        # Observer
        assert action.params["path"] == "src/old_path.py"
        assert action.modified is True
        app.push_screen_wait.assert_not_called()
        app._refresh_node.assert_called_once_with(node)


@pytest.mark.anyio
async def test_launch_editor_skips_confirmation():
    """Tests that skip_confirm=True bypasses the ConfirmScreen modal."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
        launch_editor,
    )

    # Setup local app mock to match file pattern
    app = MagicMock()
    app.is_headless = False
    app.push_screen_wait = AsyncMock()

    # Mock system_env and console_tooling
    app._system_env = MagicMock()
    app._console_tooling = MagicMock()
    app._system_env.create_temp_file.return_value = "test.log"
    app._console_tooling.find_editor.return_value = ["code"]

    # We mock the 'open' to avoid side effects and 'spawn_editor' to avoid real processes
    with patch("builtins.open", mock_open(read_data="formatted log")), \
         patch("teddy_executor.adapters.inbound.textual_plan_reviewer_previews.spawn_editor") as mock_spawn:
        result = await launch_editor(app, "initial", skip_confirm=True)

    assert result == "formatted log"
    mock_spawn.assert_called_once()
    app.push_screen_wait.assert_not_called()
