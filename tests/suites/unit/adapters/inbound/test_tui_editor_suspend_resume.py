"""
Tests for TUI editor suspend/resume feature.

Verifies that launch_editor() correctly distinguishes CLI editors
(which need suspend/resume + subprocess.run) from GUI editors
(which keep the old Popen + ConfirmScreen pattern).
Also tests the CLI diff viewer suspend path in preview_edit_diff_viewer.
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


class TestAddMessageHandler:
    """Tests for add_message_handler skip_confirm behavior."""

    @pytest.mark.anyio
    async def test_add_message_handler_skips_confirm(self):
        """When add_message_handler is called, launch_editor must be called with
        skip_confirm=True and no ConfirmScreen should be pushed."""
        from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
            add_message_handler,
        )
        from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
            ConfirmScreen,
        )

        app = MagicMock()
        app.is_headless = False
        app._console_tooling.find_editor.return_value = ["vim"]
        app.INSTRUCTION_MARKER = "---INSTRUCTIONS---"
        app.notify = MagicMock()
        app._pending_message_file = "/tmp/pending_msg.md"
        app._user_message_cache = None
        app.plan.metadata = {}
        app._system_env.create_temp_file.return_value = "/tmp/pending_msg.md"

        # Mock launch_editor to return a new message
        with patch(
            "teddy_executor.adapters.inbound.textual_plan_reviewer_previews.launch_editor",
            return_value="new message content",
        ) as mock_launch:
            # Act
            await add_message_handler(app)

            # Assert: launch_editor was called with skip_confirm=True
            mock_launch.assert_called_once()
            _, kwargs = mock_launch.call_args
            assert kwargs.get("skip_confirm") is True, (
                f"Expected skip_confirm=True, got {kwargs.get('skip_confirm')}"
            )

        # Assert: push_screen_wait was NOT called with ConfirmScreen
        if app.push_screen_wait.call_count > 0:
            for call in app.push_screen_wait.call_args_list:
                args, _ = call
                assert not any(
                    isinstance(a, type) and issubclass(a, ConfirmScreen)
                    for a in args
                ), "push_screen_wait should not be called with ConfirmScreen"

        # Assert: _user_message_cache was updated
        assert app._user_message_cache == "new message content"


class TestLaunchEditor:
    """Tests for launch_editor suspend/resume behavior."""

    @pytest.mark.anyio
    async def test_no_editor_notifies_user(self):
        """When find_editor() returns None, launch_editor must call app.notify
        with the configured message and return None."""
        from teddy_executor.adapters.inbound.textual_plan_reviewer_editor import (
            launch_editor,
        )

        app = MagicMock()
        app.is_headless = False
        app._console_tooling.find_editor.return_value = None
        app.INSTRUCTION_MARKER = "---INSTRUCTIONS---"
        app.notify = MagicMock()
        app._system_env.create_temp_file.return_value = "/tmp/fake.txt"

        # Act: call launch_editor with initial content
        result = await launch_editor(app, "initial content")

        # Assert: result is None (no editor to launch)
        assert result is None, (
            f"Expected None when no editor configured, got: {repr(result)}"
        )
        # Assert: notification is called
        app.notify.assert_called_once_with(
            "No editor configured. Please configure one in .teddy/config.yaml"
        )

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
                # Call the function
                await launch_editor(app, "initial content")

            # Assert suspend was entered (context manager)
            app.suspend.assert_called_once()

            # Clean up temp file
            os.remove(temp_path)
        finally:
            if mock_out is not None:
                os.environ["TEDDY_TEST_MOCK_EDITOR_OUTPUT"] = mock_out


class TestPreviewEditDiffViewer:
    """Tests for preview_edit_diff_viewer CLI editor suspend path."""

    @pytest.mark.anyio
    async def test_preview_edit_diff_viewer_cli_editor_triggers_suspend(self):
        """When diff viewer is a CLI editor (vim -d), preview_edit_diff_viewer
        should call app.suspend() and use subprocess.run instead of background + ConfirmScreen."""
        from teddy_executor.adapters.inbound.textual_plan_reviewer_editor import (
            preview_edit_diff_viewer,
        )
        from teddy_executor.core.domain.models.plan import ActionData

        app = MagicMock()
        app.is_headless = False
        app._console_tooling = MagicMock()
        app._console_tooling.get_diff_viewer_command.return_value = ["vim", "-d"]
        app._system_env.create_temp_file.return_value = "/tmp/before.test"
        app._system_env.delete_file = MagicMock()

        action = ActionData(
            type="EDIT",
            params={
                "path": "file.test",
                "edits": [{"find": "old", "replace": "new"}],
            },
        )
        action.pending_temp_file = "/tmp/after.test"

        before_path = "/tmp/before.test"

        with (
            patch(
                "teddy_executor.adapters.inbound.textual_plan_reviewer_editor._setup_before_file",
                return_value=before_path,
            ),
            patch(
                "teddy_executor.adapters.inbound.textual_plan_reviewer_editor.prepare_after_file",
            ),
            patch.object(app._system_env, "delete_file"),
            patch("subprocess.run") as mock_run,
        ):
            # Act
            result = await preview_edit_diff_viewer(
                app, action, ["vim", "-d"], "original content", "proposed content"
            )

            # Assert: subprocess.run was called with vim -d + before + after files
            mock_run.assert_called_once()
            call_args, _ = mock_run.call_args
            cmd = list(call_args[0])
            assert "vim" in cmd, f"Expected vim in command: {cmd}"
            assert "-d" in cmd, f"Expected -d in command: {cmd}"

            # Assert: returns True (auto-harvested)
            assert result is True, (
                f"Expected True (auto-harvest successful), got {result}"
            )

            # Assert: before file was deleted after harvest
            app._system_env.delete_file.assert_called_with(before_path)

    @pytest.mark.anyio
    async def test_preview_edit_diff_viewer_gui_editor_uses_confirm_screen(self):
        """When diff viewer is a GUI editor (code --diff), preview_edit_diff_viewer
        should use the existing background + ConfirmScreen path, not subprocess.run."""
        from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
            ConfirmScreen,
        )
        from teddy_executor.adapters.inbound.textual_plan_reviewer_editor import (
            preview_edit_diff_viewer,
        )
        from teddy_executor.core.domain.models.plan import ActionData

        app = MagicMock()
        app.is_headless = False
        app._console_tooling = MagicMock()
        app._console_tooling.get_diff_viewer_command.return_value = [
            "/usr/local/bin/code",
            "--diff",
        ]
        app._system_env.create_temp_file.return_value = "/tmp/before.test"
        app._system_env.delete_file = MagicMock()
        app._system_env.run_command = MagicMock()
        app.push_screen_wait = AsyncMock(return_value=True)

        action = ActionData(
            type="EDIT",
            params={
                "path": "file.test",
                "edits": [{"find": "old", "replace": "new"}],
            },
        )
        action.pending_temp_file = "/tmp/after.test"

        before_path = "/tmp/before.test"

        with (
            patch(
                "teddy_executor.adapters.inbound.textual_plan_reviewer_editor._setup_before_file",
                return_value=before_path,
            ),
            patch(
                "teddy_executor.adapters.inbound.textual_plan_reviewer_editor.prepare_after_file",
            ),
            patch(
                "teddy_executor.adapters.inbound.textual_plan_reviewer_editor.harvest_edit_diff",
            ) as mock_harvest,
        ):
            # Act
            result = await preview_edit_diff_viewer(
                app,
                action,
                ["/usr/local/bin/code", "--diff"],
                "original content",
                "proposed content",
            )

            # Assert: run_command is called with background=True (GUI flow)
            app._system_env.run_command.assert_called_once()
            call_args, call_kwargs = app._system_env.run_command.call_args
            assert call_kwargs.get("background") is True, (
                f"Expected background=True, got {call_kwargs}"
            )

            # Assert: push_screen_wait was called with ConfirmScreen
            app.push_screen_wait.assert_called_once()
            push_args, _ = app.push_screen_wait.call_args
            assert any(
                isinstance(a, ConfirmScreen) for a in push_args
            ), "Should push ConfirmScreen for GUI editors"

            # Assert: harvest_edit_diff was called after confirm
            mock_harvest.assert_called_once()

        # Assert: before file was deleted
        app._system_env.delete_file.assert_called_with(before_path)
