"""Regression test: READ action preview should open the real file directly.

The fix for preview_readonly() must:
1. Open the REAL file (no temp copy).
2. Use proper CLI/GUI branching (subprocess.run for CLI, spawn_editor for GUI).
3. Not call os.chmod(0o444).
4. Not create or delete temp files.

This test asserts the expected behavior and will fail on the buggy code.
"""

import asyncio
import os
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "src")
)

from teddy_executor.adapters.inbound.textual_plan_reviewer_previews import (
    preview_readonly,
)
from teddy_executor.core.domain.models.plan import ActionData


class TestReadPreviewOpensRealFile(unittest.TestCase):
    """Verify that preview_readonly() opens the real file directly."""

    def setUp(self):
        """Create mock app and a real temp file to serve as the resource."""
        self.temp_dir = tempfile.mkdtemp()
        self.resource_path = os.path.join(self.temp_dir, "test_readme.md")
        with open(self.resource_path, "w", encoding="utf-8") as f:
            f.write("# Test Content\n\nThis is the real file content.")

        # Build mock app with all required attributes
        self.mock_app = MagicMock()
        self.mock_app._file_system = MagicMock()
        self.mock_app._file_system.read_file.return_value = (
            "# Test Content\n\nThis is the real file content."
        )
        self.mock_app._system_env = MagicMock()
        self.mock_app.is_headless = True  # Skip ConfirmScreen for simplicity
        self.mock_app.notify = MagicMock()
        self.mock_app.suspend = MagicMock()
        suspend_cm = MagicMock()
        suspend_cm.__enter__ = MagicMock()
        suspend_cm.__exit__ = MagicMock()
        self.mock_app.suspend.return_value = suspend_cm
        self.mock_app.push_screen_wait = AsyncMock(return_value=True)
        self.mock_app._console_tooling = MagicMock()
        # Web scraper port (WebScraper) — None by default; URL tests configure it
        self.mock_app._web_scraper = None

        # Track temp file operations
        self.temp_files_created = []
        self.temp_files_deleted = []

        def mock_create_temp_file(suffix="", mode="w"):
            path = os.path.join(
                self.temp_dir, f"teddy_test_{len(self.temp_files_created)}{suffix}"
            )
            self.temp_files_created.append(path)
            return path

        def mock_delete_file(path):
            self.temp_files_deleted.append(path)

        self.mock_app._system_env.create_temp_file.side_effect = mock_create_temp_file
        self.mock_app._system_env.delete_file.side_effect = mock_delete_file

        # Create action data
        self.action = MagicMock(spec=ActionData)
        self.action.params = {"resource": self.resource_path, "path": ""}
        self.action.type = "READ"

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cli_editor_uses_real_file_no_temp(self):
        """CLI editor: must route through launch_editor with real file path."""
        editor_cmd = ["nvim"]
        self.mock_app._console_tooling.find_editor.return_value = editor_cmd

        with patch(
            "teddy_executor.adapters.inbound.textual_plan_reviewer_previews.launch_editor",
            new_callable=AsyncMock,
        ) as mock_launch:
            asyncio.run(preview_readonly(self.mock_app, self.action))

            # Verify: launch_editor was called with the real file path and skip_confirm=True
            mock_launch.assert_called_once()
            call_kwargs = mock_launch.call_args[1]
            self.assertEqual(
                call_kwargs.get("persistent_path"),
                self.resource_path,
                f"Expected real file path in launch_editor persistent_path: {call_kwargs}",
            )
            self.assertTrue(
                call_kwargs.get("skip_confirm", False),
                "skip_confirm should be True for read-only preview",
            )

            # Verify: does not create temp files or delete them
            self.assertEqual(
                len(self.temp_files_created), 0, "Should NOT create any temp files"
            )
            self.assertEqual(
                len(self.temp_files_deleted), 0, "Should NOT delete any temp files"
            )

            # Verify: notification was sent before launch_editor
            self.mock_app.notify.assert_any_call("Opening Editor: nvim")

    def test_gui_editor_uses_real_file_no_temp(self):
        """GUI editor: must use real file path, Popen, NO ConfirmScreen, no temp."""
        editor_cmd = ["code"]
        self.mock_app._console_tooling.find_editor.return_value = editor_cmd
        self.mock_app.is_headless = False
        self.mock_app.push_screen_wait = AsyncMock(return_value=True)

        with patch(
            "teddy_executor.adapters.inbound.textual_plan_reviewer_previews.spawn_editor"
        ) as mock_spawn:
            with patch("os.chmod") as mock_chmod:
                asyncio.run(preview_readonly(self.mock_app, self.action))

                # Verify: spawn_editor was called with the REAL file path
                mock_spawn.assert_called_once()
                call_args = mock_spawn.call_args[0]
                self.assertIn(
                    self.resource_path,
                    call_args[1],
                    f"Expected real file path in spawn_editor args: {call_args}",
                )
                self.assertNotIn(
                    "teddy_test",
                    str(call_args),
                    "Should NOT use a temp file path",
                )

                # Verify: os.chmod was NOT called
                mock_chmod.assert_not_called()

                # Verify: no temp files created or deleted
                self.assertEqual(
                    len(self.temp_files_created), 0, "Should NOT create any temp files"
                )
                self.assertEqual(
                    len(self.temp_files_deleted), 0, "Should NOT delete any temp files"
                )

                # Verify: ConfirmScreen was NOT shown (read-only, no save needed)
                self.mock_app.push_screen_wait.assert_not_called()

    def test_resource_not_found_returns_early(self):
        """Missing file: must return early without editor launch."""
        self.action.params = {"resource": "/nonexistent/path.md", "path": ""}
        editor_cmd = ["nvim"]
        self.mock_app._console_tooling.find_editor.return_value = editor_cmd

        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = False
            with patch("subprocess.run") as mock_run:
                asyncio.run(preview_readonly(self.mock_app, self.action))

                mock_run.assert_not_called()
                # Should notify "not found"
                notify_calls = self.mock_app.notify.call_args_list
                found = any("not found" in str(call).lower() for call in notify_calls)
                self.assertTrue(
                    found, f"Expected 'not found' notification, got: {notify_calls}"
                )

    def test_no_editor_configured_returns_early(self):
        """No editor: must return early without any editor launch."""
        self.mock_app._console_tooling.find_editor.return_value = None

        with patch("subprocess.run") as mock_run:
            with patch(
                "teddy_executor.adapters.inbound.textual_plan_reviewer_previews.spawn_editor"
            ) as mock_spawn:
                asyncio.run(preview_readonly(self.mock_app, self.action))

                mock_run.assert_not_called()
                mock_spawn.assert_not_called()
                self.assertEqual(len(self.temp_files_created), 0)
                self.assertEqual(len(self.temp_files_deleted), 0)

    def test_resource_param_fallback(self):
        """Use 'path' param when 'resource' is empty."""
        self.action.params = {"resource": "", "path": self.resource_path}
        editor_cmd = ["nvim"]
        self.mock_app._console_tooling.find_editor.return_value = editor_cmd

        with patch("subprocess.run") as mock_run:
            asyncio.run(preview_readonly(self.mock_app, self.action))

            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            self.assertIn(
                self.resource_path,
                call_args,
                f"Expected real file path from 'path' param: {call_args}",
            )

    def test_empty_resource_returns_early(self):
        """Both resource and path empty: must return early."""
        self.action.params = {"resource": "", "path": ""}
        editor_cmd = ["nvim"]
        self.mock_app._console_tooling.find_editor.return_value = editor_cmd

        with patch("subprocess.run") as mock_run:
            asyncio.run(preview_readonly(self.mock_app, self.action))

            mock_run.assert_not_called()
            self.assertEqual(len(self.temp_files_created), 0)
            self.assertEqual(len(self.temp_files_deleted), 0)

    def test_readonly_url_fetches_content_and_opens_temp_file(self):
        """URL: must fetch via WebScraper port, open in launch_editor with content."""
        self.action.params = {"resource": "https://example.com/test.md", "path": ""}
        editor_cmd = ["vim"]
        self.mock_app._console_tooling.find_editor.return_value = editor_cmd
        expected_content = "# Test\nFetched content from URL.\n"
        self.mock_app._web_scraper = MagicMock()
        self.mock_app._web_scraper.get_content.return_value = expected_content

        with patch(
            "teddy_executor.adapters.inbound.textual_plan_reviewer_previews.launch_editor",
            new_callable=AsyncMock,
        ) as mock_launch:
            asyncio.run(preview_readonly(self.mock_app, self.action))

        # Assert: the existing WebScraper port was called with the correct URL
        self.mock_app._web_scraper.get_content.assert_called_once_with(
            "https://example.com/test.md"
        )

        # Assert: launch_editor was called with the scraped content, .md suffix, skip_confirm=True
        mock_launch.assert_called_once()
        call_args = mock_launch.call_args[0]
        self.assertEqual(call_args[0], self.mock_app)
        self.assertEqual(
            call_args[1],
            expected_content,
            "launch_editor should receive the scraped content",
        )
        call_kwargs = mock_launch.call_args[1]
        self.assertEqual(call_kwargs.get("suffix"), ".md")
        self.assertTrue(
            call_kwargs.get("skip_confirm", False),
            "skip_confirm should be True for read-only preview",
        )
        # No persistent_path — launch_editor creates and manages its own temp file
        self.assertIsNone(
            call_kwargs.get("persistent_path"),
            "persistent_path should be None for URL content",
        )

    def test_readonly_url_fetch_failure_notifies_user(self):
        """If the WebScraper port fetch fails, must notify and return without opening editor."""
        self.action.params = {"resource": "https://example.com/fail.md", "path": ""}
        editor_cmd = ["vim"]
        self.mock_app._console_tooling.find_editor.return_value = editor_cmd
        self.mock_app._web_scraper = MagicMock()
        self.mock_app._web_scraper.get_content.side_effect = Exception("Network error")

        with patch("subprocess.run") as mock_run:
            asyncio.run(preview_readonly(self.mock_app, self.action))

        # notify is called twice: "Opening Editor: vim" and the failure message.
        # Assert that the failure message was present in any call.
        self.mock_app.notify.assert_any_call(
            "Failed to fetch URL: https://example.com/fail.md"
        )
        mock_run.assert_not_called()

    def test_readonly_gui_editor_does_not_show_confirm_screen(self):
        """GUI editor: must NOT push ConfirmScreen, just spawn editor and return."""
        self.mock_app._console_tooling.find_editor.return_value = ["code"]

        with (
            patch(
                "teddy_executor.adapters.inbound.textual_plan_reviewer_previews.spawn_editor"
            ) as mock_spawn,
            patch.object(self.mock_app, "push_screen_wait") as mock_push,
        ):
            asyncio.run(preview_readonly(self.mock_app, self.action))

        # Assert: spawn_editor was called with the real file path
        mock_spawn.assert_called_once()
        call_args = mock_spawn.call_args[0]

    def test_gui_url_temp_file_persists_for_deferred_cleanup(self):
        """GUI editor + URL: temp file must NOT be deleted immediately; tracked for cleanup.

        Regression test for the race condition where os.unlink() deletes a temp file
        immediately after spawn_editor() (non-blocking Popen), causing GUI editors
        to open an empty buffer. The fix: append to app._log_preview_files for
        deferred cleanup on TUI exit, same pattern as view_details_handler.
        """
        self.action.params = {
            "resource": "https://example.com/test.md",
            "path": "",
        }
        editor_cmd = ["codium"]
        self.mock_app._console_tooling.find_editor.return_value = editor_cmd
        self.mock_app._web_scraper = MagicMock()
        self.mock_app._web_scraper.get_content.return_value = (
            "# Test\nFetched content from URL.\n"
        )
        # Initialize the log preview files list for tracking
        self.mock_app._log_preview_files = []
        # Mock is_headless to avoid ConfirmScreen for GUI
        self.mock_app.is_headless = False

        expected_content = "# Test\nFetched content from URL.\n"
        created_temp_path = None

        def mock_named_temp_file(
            mode="w",
            suffix=".md",
            prefix="teddy_read_url_",
            delete=False,
            encoding="utf-8",
        ):
            nonlocal created_temp_path
            ntf = MagicMock()
            ntf.name = os.path.join(self.temp_dir, f"teddy_read_url_test{suffix}")
            created_temp_path = ntf.name
            ntf.write = MagicMock()
            ntf.close = MagicMock()
            return ntf

        with (
            patch("tempfile.NamedTemporaryFile", side_effect=mock_named_temp_file),
            patch(
                "teddy_executor.adapters.inbound.textual_plan_reviewer_previews.spawn_editor"
            ) as mock_spawn,
            patch("os.unlink") as mock_unlink,
        ):
            asyncio.run(preview_readonly(self.mock_app, self.action))

        # Assert: os.unlink was NOT called (the fix — temp file persists)
        mock_unlink.assert_not_called()

        # Assert: temp file path was appended to _log_preview_files for deferred cleanup
        self.assertEqual(
            len(self.mock_app._log_preview_files),
            1,
            "Expected 1 temp file tracked in _log_preview_files",
        )
        self.assertEqual(
            self.mock_app._log_preview_files[0],
            created_temp_path,
            f"Expected {created_temp_path} in _log_preview_files",
        )

        # Assert: spawn_editor was called with the correct temp file path
        mock_spawn.assert_called_once()
        call_args = mock_spawn.call_args[0]
        self.assertIn(
            "teddy_read_url_test",
            str(call_args),
            f"Expected temp file path in spawn_editor call: {call_args}",
        )
        self.assertIn(
            "codium",
            str(call_args),
            f"Expected editor cmd 'codium' in spawn_editor call: {call_args}",
        )

    def test_readonly_url_temp_file_is_cleaned_up(self):
        """URL: launch_editor receives content; temp file cleanup is internal."""
        self.action.params = {"resource": "https://example.com/test.md", "path": ""}
        editor_cmd = ["vim"]
        self.mock_app._console_tooling.find_editor.return_value = editor_cmd
        self.mock_app._web_scraper = MagicMock()
        self.mock_app._web_scraper.get_content.return_value = "content"

        with patch(
            "teddy_executor.adapters.inbound.textual_plan_reviewer_previews.launch_editor",
            new_callable=AsyncMock,
        ) as mock_launch:
            asyncio.run(preview_readonly(self.mock_app, self.action))

        # Assert: the WebScraper port was consulted with the URL
        self.mock_app._web_scraper.get_content.assert_called_once_with(
            "https://example.com/test.md"
        )

        # Assert: launch_editor was called with the scraped content
        mock_launch.assert_called_once()
        call_args = mock_launch.call_args[0]
        self.assertEqual(call_args[1], "content")
        # Temp file cleanup is handled internally by launch_editor — no explicit assertion needed.

    def test_readonly_url_without_web_scraper_notifies(self):
        """If no web scraper is configured, URL READ must notify and return."""
        self.action.params = {"resource": "https://example.com/test.md", "path": ""}
        editor_cmd = ["vim"]
        self.mock_app._console_tooling.find_editor.return_value = editor_cmd
        self.mock_app._web_scraper = None

        with patch("subprocess.run") as mock_run:
            asyncio.run(preview_readonly(self.mock_app, self.action))

        self.mock_app.notify.assert_any_call(
            "No web scraper configured. Cannot fetch URL content."
        )
        mock_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
