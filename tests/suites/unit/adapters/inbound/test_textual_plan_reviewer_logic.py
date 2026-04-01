import pytest
from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
    extract_status_emoji,
)


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
