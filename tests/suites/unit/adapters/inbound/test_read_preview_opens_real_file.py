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
        """CLI editor: must use real file path, no temp file, no chmod."""
        editor_cmd = ["nvim"]
        self.mock_app._console_tooling.find_editor.return_value = editor_cmd

        with patch("subprocess.run") as mock_run:
            with patch("os.chmod") as mock_chmod:
                asyncio.run(preview_readonly(self.mock_app, self.action))

                # Verify: subprocess.run was called with the REAL file path
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                self.assertIn(
                    self.resource_path,
                    call_args,
                    f"Expected real file path in subprocess.run args: {call_args}",
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

                # Verify: suspend was called (CLI editor path)
                self.mock_app.suspend.assert_called_once()

    def test_gui_editor_uses_real_file_no_temp(self):
        """GUI editor: must use real file path, Popen, ConfirmScreen, no temp."""
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

                # Verify: ConfirmScreen was shown
                self.mock_app.push_screen_wait.assert_called_once()

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


if __name__ == "__main__":
    unittest.main()
