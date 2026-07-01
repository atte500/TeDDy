#!/usr/bin/env python3
"""
Regression test: TUI content harvest before execution.

Verifies that harvest_action_content() correctly transfers modified content
from pending_temp_file to action.params for all affected action types
(CREATE, EXECUTE, RESEARCH) and does NOT modify unaffected types (EDIT).
"""

import os
import tempfile


from teddy_executor.adapters.inbound.textual_plan_reviewer_execution import (
    harvest_action_content,
)
from teddy_executor.core.domain.models.plan import ActionData


class TestTuiContentHarvest:
    """Regression: content modified via editor must be harvested before execution."""

    def setup_action(
        self, action_type: str, param_key: str, original_val: str
    ) -> ActionData:
        """Create an ActionData and write modified content to a temp file."""
        action = ActionData(
            type=action_type,
            params={param_key: original_val},
            description=f"Test {action_type} action",
        )
        return action

    def test_harvest_create_content(self):
        """CREATE: original content replaced with modified temp file content."""
        action = self.setup_action("CREATE", "content", "original content")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("modified content")
            temp_path = f.name
        action.pending_temp_file = temp_path

        harvest_action_content(action, "")

        assert action.params["content"] == "modified content"
        assert action.pending_temp_file is None
        assert not os.path.exists(temp_path)

    def test_harvest_execute_command(self):
        """EXECUTE: original command replaced with modified temp file content."""
        action = self.setup_action("EXECUTE", "command", "echo hello")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write("echo world")
            temp_path = f.name
        action.pending_temp_file = temp_path

        harvest_action_content(action, "")

        assert action.params["command"] == "echo world"
        assert action.pending_temp_file is None
        assert not os.path.exists(temp_path)

    def test_harvest_research_queries(self):
        """RESEARCH: original queries replaced with modified temp file content."""
        action = self.setup_action("RESEARCH", "queries", ["old query"])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("new query")
            temp_path = f.name
        action.pending_temp_file = temp_path

        harvest_action_content(action, "")

        assert action.params["queries"] == "new query"
        assert action.pending_temp_file is None
        assert not os.path.exists(temp_path)

    def test_harvest_edit_unaffected(self):
        """EDIT: params should NOT be modified by harvest."""
        action = self.setup_action("EDIT", "edits", [{"find": "old", "replace": "new"}])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("modified content")
            temp_path = f.name
        action.pending_temp_file = temp_path

        harvest_action_content(action, "")

        assert "edits" in action.params
        assert action.params["edits"] == [{"find": "old", "replace": "new"}]
        # Temp file should still be cleaned up
        assert action.pending_temp_file is None
        assert not os.path.exists(temp_path)

    def test_harvest_no_pending_file(self):
        """No pending_temp_file set: params unchanged, no error."""
        action = self.setup_action("CREATE", "content", "original")
        harvest_action_content(action, "")
        assert action.params["content"] == "original"

    def test_harvest_file_does_not_exist(self):
        """pending_temp_file points to non-existent file: params unchanged, no error."""
        action = self.setup_action("CREATE", "content", "original")
        action.pending_temp_file = "/tmp/nonexistent_file_12345.txt"
        harvest_action_content(action, "")
        assert action.params["content"] == "original"

    def test_harvest_empty_temp_file(self):
        """Temp file exists but is empty: content should be set to empty string."""
        action = self.setup_action("CREATE", "content", "original")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")
            temp_path = f.name
        action.pending_temp_file = temp_path

        harvest_action_content(action, "")

        assert action.params["content"] == ""
        assert action.pending_temp_file is None
        assert not os.path.exists(temp_path)
