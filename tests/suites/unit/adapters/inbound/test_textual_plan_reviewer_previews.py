import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
    preview_create,
    preview_prompt,
)
from teddy_executor.core.domain.models.plan import ActionData


@pytest.mark.anyio
async def test_preview_prompt_updates_user_response():
    """Verify that preview_prompt updates the action's user_response after confirmation."""
    # Setup
    app = MagicMock()
    app.push_screen_wait = AsyncMock(side_effect=[True])  # ConfirmScreen returns True

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
        app._refresh_node.assert_called_once_with(node)


@pytest.mark.anyio
async def test_preview_create_updates_path_and_content():
    """Verify that preview_create updates both path and content after confirmation."""
    # Setup
    app = MagicMock()
    # 1. New Path, 2. Confirmation
    app.push_screen_wait = AsyncMock(side_effect=["src/new_path.py", True])

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
        assert action.params["path"] == "src/new_path.py"
        assert action.params["content"] == "new content"
        assert action.modified is True
        app._refresh_node.assert_called_once_with(node)
