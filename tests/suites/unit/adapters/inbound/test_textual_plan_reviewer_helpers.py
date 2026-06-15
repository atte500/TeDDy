from unittest.mock import MagicMock


from teddy_executor.core.domain.models.execution_report import ActionLog, ActionStatus
from teddy_executor.core.domain.models.project_context import (
    ContextItem,
    ProjectContext,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_execution import (
    format_action_log,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
    populate_context_detail,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import DetailItem


def test_format_action_log_success():
    """Tests formatting of a successful action log."""
    log = ActionLog(
        action_type="CREATE",
        params={"path": "test.txt"},
        status=ActionStatus.SUCCESS,
        details="File created successfully.",
    )

    formatted = format_action_log(log)

    assert "- **Overall Status:** SUCCESS" in formatted
    assert "### `CREATE`: [test.txt](/test.txt)" in formatted
    assert "- **Status:** SUCCESS" in formatted
    assert "- **Details:** `File created successfully.`" in formatted


def test_format_action_log_failure_with_output():
    """Tests formatting of a failed EXECUTE action with stdout/stderr."""
    log = ActionLog(
        action_type="EXECUTE",
        params={"command": "ls non_existent"},
        status=ActionStatus.FAILURE,
        failed_command="ls non_existent",
        details={
            "return_code": 1,
            "stdout": "out",
            "stderr": "err",
            "diff": "--- a\n+++ b",
            "failed_command": "ls non_existent",
        },
    )

    formatted = format_action_log(log)

    assert "- **Overall Status:** FAILURE" in formatted
    assert "- **Status:** FAILURE" in formatted
    assert "- **Failed Command:** `ls non_existent`" in formatted
    assert "- **Return Code:** `1`" in formatted
    assert "#### `stdout`\n```text\nout\n```" in formatted
    assert "#### `stderr`\n```text\nerr\n```" in formatted
    assert "#### `diff`\n```diff\n--- a\n+++ b\n```" in formatted


def test_populate_context_detail_shows_merged_system_line():
    """
    Scenario: Context Aggregate View with content_tokens
    Tests that populate_context_detail() computes system_info_tokens from
    content_tokens - selected_item_tokens and shows the merged System line.
    """
    # Arrange
    app = MagicMock()
    pane = []
    data = {"type": "CONTEXT_ROOT"}

    # Create a ProjectContext with content_tokens and selected items
    app.project_context = ProjectContext(
        header="H",
        content="C",
        items=[
            ContextItem(
                path="session_file.py",
                token_count=100,
                git_status="",
                scope="Session",
                selected=True,
            ),
            ContextItem(
                path="turn_file.py",
                token_count=50,
                git_status="",
                scope="Turn",
                selected=True,
            ),
            ContextItem(
                path="history_file.py",
                token_count=25,
                git_status="",
                scope="Session",
                selected=True,
            ),
        ],
        agent_name="Developer",
        system_prompt_tokens=500,
        content_tokens=1000,
        total_window=128000,
    )

    # Act
    populate_context_detail(app, pane, data)

    # Assert
    # Extract DetailItem values from the pane
    detail_map = {
        item.data["key"]: item.data["val"]
        for item in pane
        if isinstance(item, DetailItem)
    }

    # Total Context should be content_tokens + system_prompt_tokens
    # 1000 + 500 = 1500 -> 1.5k / 128k tokens
    assert "Total Context" in detail_map
    assert "1.5k / 128k tokens" in detail_map["Total Context"]

    # System should be (system_prompt_tokens + system_info_tokens)
    # system_info_tokens = content_tokens - sum(selected_item_tokens)
    # = 1000 - (100 + 50 + 25) = 825
    # System = 500 + 825 = 1325 -> 1.3k
    assert "• System" in detail_map
    assert "1.3k" in detail_map["• System"]

    # Session, Turn, History should remain unchanged
    assert "• Session" in detail_map
    assert "• Turn" in detail_map
    assert "• History" in detail_map


def test_populate_context_detail_system_info_tokens_equals_content_tokens_when_no_files_selected():
    """
    Scenario: No files selected
    Tests that when selected_file_tokens == 0, system_info_tokens equals content_tokens
    and System shows all of it plus the system prompt.
    """
    # Arrange
    app = MagicMock()
    pane = []
    data = {"type": "CONTEXT_ROOT"}

    # Create a ProjectContext with content_tokens but NO selected items
    app.project_context = ProjectContext(
        header="H",
        content="C",
        items=[
            ContextItem(
                path="session_file.py",
                token_count=100,
                git_status="",
                scope="Session",
                selected=False,  # Not selected
            ),
        ],
        agent_name="Developer",
        system_prompt_tokens=500,
        content_tokens=1000,
        total_window=128000,
    )

    # Act
    populate_context_detail(app, pane, data)

    # Assert
    detail_map = {
        item.data["key"]: item.data["val"]
        for item in pane
        if isinstance(item, DetailItem)
    }

    # Total Context should be content_tokens + system_prompt_tokens
    assert "Total Context" in detail_map
    assert "1.5k / 128k tokens" in detail_map["Total Context"]

    # System should be (system_prompt_tokens + system_info_tokens)
    # system_info_tokens = content_tokens - 0 = 1000
    # System = 500 + 1000 = 1500 -> 1.5k
    assert "• System" in detail_map
    assert "1.5k" in detail_map["• System"]
