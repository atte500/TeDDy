from unittest.mock import create_autospec
from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
    populate_context_detail,
)
from teddy_executor.core.domain.models.project_context import (
    ProjectContext,
    ContextItem,
)


def test_populate_context_detail_shows_sentinel_on_zero_window():
    # Arrange
    # Use create_autospec to prevent mock poisoning (TID251)
    mock_app = create_autospec(ReviewerApp, instance=True)

    # Mock items to ensure aggregate logic runs
    item = ContextItem("file.py", 1500, "", "Session", True)

    mock_app.project_context = ProjectContext(
        header="",
        content="",
        items=[item],
        system_prompt_tokens=1000,
        content_tokens=1500,
        total_window=0,  # Sentinel value
    )
    pane = []

    # Act
    populate_context_detail(mock_app, pane, None)

    # Assert
    # Total = 1500 + 1000 = 2500 -> 2.5k
    detail_labels = [getattr(item, "data", {}).get("key") for item in pane]
    detail_values = [getattr(item, "data", {}).get("val") for item in pane]

    assert "Total Context" in detail_labels
    idx = detail_labels.index("Total Context")
    # Expected: "2.5k / ??? tokens"
    # Actual: "2.5k / 0k tokens" (expected failure)
    assert detail_values[idx] == "2.5k / ??? tokens"
