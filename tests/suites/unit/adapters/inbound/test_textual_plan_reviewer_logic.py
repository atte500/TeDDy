import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
    edit_action_logic,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
    extract_status_emoji,
)
from teddy_executor.core.domain.models.plan import ActionData


@pytest.mark.anyio
async def test_edit_action_logic_branches_to_prompt():
    """Verify that edit_action_logic calls do_preview_logic for PROMPT type."""
    # Setup
    app = MagicMock()
    node = MagicMock()
    action = ActionData(type="PROMPT", params={"message": "What is your name?"})

    # We mock do_preview_logic which is called for complex/fallback types
    mock_preview = AsyncMock()
    with patch(
        "teddy_executor.adapters.inbound.textual_plan_reviewer_previews.do_preview_logic",
        mock_preview,
    ):
        # Driver
        await edit_action_logic(app, node, action)

    # Observer
    mock_preview.assert_called_once_with(app, node, action)


@pytest.mark.parametrize(
    "raw_status, expected_emoji",
    [
        ("Green 🟢", "🟢"),
        ("Yellow 🟡", "🟡"),
        ("Red 🔴", "🔴"),
        ("NoEmoji", ""),
        ("", ""),
        ("Trailing space 🟢 ", "🟢"),
        (" 🟢 Leading space", "🟢"),
        ("Multiple 🟢 Emojis 🟡", "🟡"),
    ],
)
def test_extract_status_emoji(raw_status, expected_emoji):
    """Verify the emoji extraction helper handles various formats correctly."""
    assert extract_status_emoji(raw_status) == expected_emoji
