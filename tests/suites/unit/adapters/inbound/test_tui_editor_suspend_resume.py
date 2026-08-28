"""
Tests for TUI editor suspend/resume feature.

Verifies that launch_editor() correctly distinguishes CLI editors
(which need suspend/resume + subprocess.run) from GUI editors
(which keep the old Popen + ConfirmScreen pattern).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from teddy_executor.adapters.inbound.textual_plan_reviewer_editor import (
    _is_cli_editor,
)


class TestIsCliEditor:
    """Unit tests for _is_cli_editor classification."""

    def test_known_cli_editors_return_true(self):
        """Vim, nvim, nano, etc. should be classified as CLI editors."""
        cli_editors = [
            ["vim"],
            ["nvim", "--clean"],
            ["nano"],
            ["micro"],
            ["emacs", "-nw"],
            ["vi"],
            ["helix"],
            ["hx"],
            ["kak"],
        ]
        for cmd in cli_editors:
            assert _is_cli_editor(cmd), f"{cmd} should be classified as CLI"

    def test_gui_editors_return_false(self):
        """Code, cursor, etc. should NOT be classified as CLI editors."""
        gui_editors = [
            ["code"],
            ["code", "--wait", "."],
            ["cursor"],
            ["subl"],
            ["goland"],
            ["pycharm"],
        ]
        for cmd in gui_editors:
            assert not _is_cli_editor(cmd), f"{cmd} should NOT be classified as CLI"

    def test_none_or_empty_returns_false(self):
        """If editor_cmd is None or empty, return False."""
        assert _is_cli_editor(None) is False
        assert _is_cli_editor([]) is False


class TestLaunchEditor:
    """Tests for launch_editor suspend/resume behavior."""

    @pytest.mark.anyio
    async def test_cli_editor_triggers_suspend(self):
        """For a CLI editor (vim), app.suspend() must be called."""
        import os
        import tempfile

        from teddy_executor.adapters.inbound.textual_plan_reviewer_editor import (
            launch_editor,
        )

        # Ensure the mock env var is not set so we go through the real path
        mock_out = os.environ.pop("TEDDY_TEST_MOCK_EDITOR_OUTPUT", None)
        try:
            app = MagicMock()
            app.is_headless = False
            app._console_tooling.find_editor.return_value = ["vim"]
            app.INSTRUCTION_MARKER = "---INSTRUCTIONS---"
            app.notify = MagicMock()

            # Create a real temp file to simulate editor output
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False
            ) as f:
                f.write("edited content")
                temp_path = f.name
            app._system_env.create_temp_file.return_value = temp_path
            app._system_env.delete_file = MagicMock()

            # Mock subprocess.run to prevent real vim invocation
            with patch("subprocess.run", return_value=MagicMock()):
                # Mock push_screen_wait to return True (user confirms)
                app.push_screen_wait = AsyncMock(return_value=True)
                # Call the function
                await launch_editor(app, "initial content")

            # Assert suspend was entered (context manager)
            app.suspend.assert_called_once()
            # Assert ConfirmScreen was shown (deferred harvest)
            app.push_screen_wait.assert_called_once()

            # Clean up temp file
            os.remove(temp_path)
        finally:
            if mock_out is not None:
                os.environ["TEDDY_TEST_MOCK_EDITOR_OUTPUT"] = mock_out
