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
                    isinstance(a, type) and issubclass(a, ConfirmScreen) for a in args
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


class TestReconstructFromDiff:
    """Unit tests for reconstruct_from_diff pure function.

    Covering all edge cases from the vertical slice:
    - Empty diff, only additions, only deletions, mixed, modified lines, headers
    """

    @pytest.mark.parametrize(
        ("diff_input", "expected"),
        [
            # Empty / no diff
            pytest.param("", "", id="empty_string"),
            # Only context lines (no + or -)
            pytest.param(
                "line1\nline2\nline3\n",
                "line1\nline2\nline3\n",
                id="only_context_lines",
            ),
            # Only additions (no deletions)
            pytest.param(
                "--- a/test.txt (original)\n"
                "+++ b/test.txt (proposed)\n"
                "@@ -1,0 +1,2 @@\n"
                "+added line 1\n"
                "+added line 2\n",
                "added line 1\nadded line 2\n",
                id="only_additions",
            ),
            # Only deletions (no additions)
            pytest.param(
                "--- a/test.txt (original)\n"
                "+++ b/test.txt (proposed)\n"
                "@@ -1,3 +1,0 @@\n"
                "-removed line 1\n"
                "-removed line 2\n"
                "-removed line 3\n",
                "",
                id="only_deletions",
            ),
            # Mixed: context, deletions, and additions
            # Unified diff context lines have a leading space prefix
            pytest.param(
                "--- a/test.txt (original)\n"
                "+++ b/test.txt (proposed)\n"
                "@@ -1,5 +1,5 @@\n"
                " context_line_1\n"
                "-removed_line\n"
                "+added_line\n"
                " context_line_2\n"
                "-removed_line_2\n"
                "+added_line_2\n"
                " context_line_3\n",
                " context_line_1\n"
                "added_line\n"
                " context_line_2\n"
                "added_line_2\n"
                " context_line_3\n",
                id="mixed_modifications",
            ),
            # Modified `-` lines (user edited them — harmlessly discarded)
            pytest.param(
                "--- a/test.txt (original)\n"
                "+++ b/test.txt (proposed)\n"
                "@@ -1,2 +1,2 @@\n"
                "- this line was removed but user modified it\n"
                "+replacement line\n",
                "replacement line\n",
                id="modified_minus_lines_harmless",
            ),
            # Modified `+` lines (user edited — should be kept with prefix stripped)
            # Context lines in unified diff have a leading space prefix
            pytest.param(
                "--- a/test.txt (original)\n"
                "+++ b/test.txt (proposed)\n"
                "@@ -1,2 +1,2 @@\n"
                " context\n"
                "+user edited this line\n",
                " context\nuser edited this line\n",
                id="modified_plus_lines_kept",
            ),
            # User added new lines without prefix (context lines)
            # Context lines in unified diff have a leading space prefix
            pytest.param(
                "--- a/test.txt (original)\n"
                "+++ b/test.txt (proposed)\n"
                "@@ -1,2 +1,4 @@\n"
                " context_1\n"
                " user_added_context_line\n"
                "+official_addition\n"
                " context_2\n",
                " context_1\n user_added_context_line\nofficial_addition\n context_2\n",
                id="user_added_context_lines",
            ),
            # Fully modified content (multiple hunks)
            pytest.param(
                "--- a/file.py (original)\n"
                "+++ b/file.py (proposed)\n"
                "@@ -1,5 +1,5 @@\n"
                " def old_function():\n"
                "-    return old_implementation\n"
                "+    return new_implementation\n"
                " \n"
                "@@ -10,3 +10,6 @@\n"
                " def unchanged():\n"
                "     pass\n"
                "+\n"
                "+def new_function():\n"
                '+    return "added later"\n',
                " def old_function():\n"
                "    return new_implementation\n"
                " \n"
                " def unchanged():\n"
                "     pass\n"
                "\n"
                "def new_function():\n"
                '    return "added later"\n',
                id="fully_modified_content",
            ),
        ],
    )
    def test_reconstruct_from_diff(self, diff_input: str, expected: str):
        """reconstruct_from_diff should correctly handle all annotated diff patterns."""
        from teddy_executor.adapters.inbound.textual_plan_reviewer_editor import (
            reconstruct_from_diff,
        )

        result = reconstruct_from_diff(diff_input)
        assert result == expected, f"Expected:\n{expected!r}\n\nGot:\n{result!r}"


class TestGenerateAnnotatedDiffContent:
    """Unit tests for _generate_annotated_diff_content pure function."""

    # ------------------------------------------------------------------ #
    # Helper assertion methods (no decorators — used by test method only)
    # ------------------------------------------------------------------ #

    def _assert_contains_header(self, result: str) -> None:
        """Assert that the result starts with the TeDDy header prefix."""
        assert result.startswith("# TeDDy Change Preview"), (
            f"Expected header prefix, got:\n{result[:100]}"
        )
        assert "TeDDy Change Preview" in result, (
            f"Expected header 'TeDDy Change Preview' in output, got:\n{result}"
        )

    def _assert_contains_path(self, result: str, path_str: str) -> None:
        """Assert that the path string appears in the result."""
        assert path_str in result, (
            f"Expected path '{path_str}' in output, got:\n{result}"
        )

    def _assert_contains_diff_markers(self, result: str) -> None:
        """Assert that @@ hunk markers are present in the result."""
        assert "@@" in result, f"Expected @@ hunk markers in output, got:\n{result}"

    def _assert_has_addition_lines(self, result: str) -> None:
        """Assert that addition lines ('+' prefix) are present."""
        assert "\\+" in result or "\n+" in result or result.startswith("+"), (
            f"Expected addition lines ('+' prefix) in output, got:\n{result}"
        )

    def _assert_has_deletion_lines(self, result: str) -> None:
        """Assert that deletion lines ('-' prefix) are present."""
        assert "\\-" in result or "\n-" in result or result.startswith("-"), (
            f"Expected deletion lines ('-' prefix) in output, got:\n{result}"
        )

    def _assert_empty_diff(self, result: str) -> None:
        """Assert that no diff content markers (+, -, @@) are present."""
        non_header_lines = []
        for line in result.splitlines():
            if line.startswith("+") or line.startswith("-"):
                non_header_lines.append(line)
            elif line.startswith("@@"):
                non_header_lines.append(line)
        assert len(non_header_lines) == 0, (
            f"Expected no diff content for identical inputs, got diff lines:\n"
            f"{non_header_lines}\nFull output:\n{result}"
        )

    # ------------------------------------------------------------------ #
    # Parametrized test — decorator MUST be directly above the test method
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize(
        ("original", "proposed", "path_str", "assertions"),
        [
            pytest.param(
                "line1\nline2\n",
                "line1\nmodified\n",
                "test.txt",
                {
                    "contains_header": True,
                    "contains_path": True,
                    "contains_diff_markers": True,
                    "has_addition_lines": True,
                    "has_deletion_lines": False,
                    "empty_diff": False,
                },
                id="basic_diff",
            ),
            pytest.param(
                "same content\n",
                "same content\n",
                "file.py",
                {
                    "contains_header": True,
                    "contains_path": False,
                    "contains_diff_markers": False,
                    "has_addition_lines": False,
                    "has_deletion_lines": False,
                    "empty_diff": True,
                },
                id="empty_diff_identical_content",
            ),
            pytest.param(
                "line1\nline2\nline3\n",
                "line1\nline2\nline3\nline4\nline5\n",
                "additions.txt",
                {
                    "contains_header": True,
                    "contains_path": True,
                    "contains_diff_markers": True,
                    "has_addition_lines": True,
                    "has_deletion_lines": False,
                    "empty_diff": False,
                },
                id="only_additions",
            ),
            pytest.param(
                "line1\nline2\nline3\n",
                "line1\n",
                "deletions.txt",
                {
                    "contains_header": True,
                    "contains_path": True,
                    "contains_diff_markers": True,
                    "has_addition_lines": False,
                    "has_deletion_lines": True,
                    "empty_diff": False,
                },
                id="only_deletions",
            ),
            pytest.param(
                "def old():\n    return 1\n",
                "def new():\n    return 2\n",
                "mixed.py",
                {
                    "contains_header": True,
                    "contains_path": True,
                    "contains_diff_markers": True,
                    "has_addition_lines": True,
                    "has_deletion_lines": True,
                    "empty_diff": False,
                },
                id="mixed_additions_and_deletions",
            ),
            pytest.param(
                "unchanged\n",
                "unchanged\n",
                "",
                {
                    "contains_header": True,
                    "contains_path": False,
                    "contains_diff_markers": False,
                    "has_addition_lines": False,
                    "has_deletion_lines": False,
                    "empty_diff": True,
                },
                id="empty_path_str",
            ),
            pytest.param(
                "def a():\n    pass\n\ndef b():\n    pass\n\ndef c():\n    pass\n",
                "def a():\n    return 1\n\ndef b():\n    pass\n\ndef c():\n    return 3\n",
                "multi_hunk.py",
                {
                    "contains_header": True,
                    "contains_path": True,
                    "contains_diff_markers": True,
                    "has_addition_lines": True,
                    "has_deletion_lines": True,
                    "empty_diff": False,
                },
                id="multiple_hunks",
            ),
            pytest.param(
                "content",
                "new content",
                "path/with spaces and (special).txt",
                {
                    "contains_header": True,
                    "contains_path": True,
                    "contains_diff_markers": True,
                    "has_addition_lines": True,
                    "has_deletion_lines": True,
                    "empty_diff": False,
                },
                id="special_characters_in_path",
            ),
        ],
    )
    def test_generate_annotated_diff_content(
        self, original: str, proposed: str, path_str: str, assertions: dict
    ):
        """_generate_annotated_diff_content should produce annotated unified diff output."""
        from teddy_executor.adapters.inbound.textual_plan_reviewer_editor import (
            _generate_annotated_diff_content,
        )

        result = _generate_annotated_diff_content(original, proposed, path_str)

        # Every output must start with the TeDDy header
        self._assert_contains_header(result)

        if assertions.get("contains_path"):
            self._assert_contains_path(result, path_str)

        if assertions.get("contains_diff_markers"):
            self._assert_contains_diff_markers(result)

        if assertions.get("has_addition_lines"):
            self._assert_has_addition_lines(result)

        if assertions.get("has_deletion_lines"):
            self._assert_has_deletion_lines(result)

        if assertions.get("empty_diff"):
            self._assert_empty_diff(result)


class TestPreviewEditDiffViewer:
    """Tests for preview_edit_diff_viewer CLI editor suspend path."""

    @pytest.mark.anyio
    async def test_preview_edit_diff_viewer_cli_editor_triggers_suspend(self):
        """When diff viewer is a CLI editor (vim), preview_edit_diff_viewer
        should generate an annotated .diff file, launch the editor with a single file,
        and reconstruct the edited content."""
        from teddy_executor.adapters.inbound.textual_plan_reviewer_editor import (
            preview_edit_diff_viewer,
        )
        from teddy_executor.core.domain.models.plan import ActionData

        app = MagicMock()
        app.is_headless = False
        app._console_tooling = MagicMock()
        app._console_tooling.get_diff_viewer_command.return_value = ["vim"]
        app._system_env.create_temp_file.return_value = "/tmp/wont_be_used.txt"
        app._system_env.delete_file = MagicMock()

        action = ActionData(
            type="EDIT",
            params={
                "path": "file.test",
                "edits": [{"find": "old", "replace": "new"}],
            },
        )
        action.pending_temp_file = "/tmp/after.test"

        original = "line1\nline2\n"
        proposed = "line1\nmodified\n"

        # Predictable path for the annotated diff temp file
        import os  # noqa: PLC0415
        annotated_path = f"/tmp/teddy_edit_diff_{os.getpid()}.diff"

        with (
            patch(
                "teddy_executor.adapters.inbound.textual_plan_reviewer_editor.prepare_after_file",
            ),
            patch(
                "teddy_executor.adapters.inbound.textual_plan_reviewer_editor"
                "._generate_annotated_diff_content",
                return_value="mocked annotated diff content",
            ) as mock_generate,
            patch(
                "teddy_executor.adapters.inbound.textual_plan_reviewer_editor"
                ".reconstruct_from_diff",
                return_value="line1\nmodified\n",
            ) as mock_reconstruct,
            patch("tempfile.NamedTemporaryFile") as mock_tempfile,
            patch("subprocess.run") as mock_run,
            patch(
                "teddy_executor.adapters.inbound.textual_plan_reviewer_editor"
                "._setup_before_file",
            ) as mock_setup_before,
        ):
            # Mock the tempfile context manager to return a predictable path
            mock_ntf = MagicMock()
            mock_ntf.name = annotated_path
            mock_ntf.close = MagicMock()
            mock_tempfile.return_value = mock_ntf

            # Simulate the editor writing the content back to the annotated file
            def simulate_editor_save(args, **kwargs) -> None:
                """Write mock diff content to simulate user editing."""
                with open(annotated_path, "w", encoding="utf-8") as f:
                    f.write(
                        "# TeDDy Change Preview — Single Annotated File\n"
                        "# ... (header)\n"
                        "--- a/file.test (original)\n"
                        "+++ b/file.test (proposed)\n"
                        "@@ -1,2 +1,2 @@\n"
                        " line1\n"
                        "-line2\n"
                        "+modified\n"
                    )
            mock_run.side_effect = simulate_editor_save

            # Act
            result = await preview_edit_diff_viewer(
                app, action, ["vim"], original, proposed
            )

            # Assert: _generate_annotated_diff_content was called with correct args
            mock_generate.assert_called_once_with(original, proposed, "file.test")

            # Assert: subprocess.run was called with vim + single .diff file
            mock_run.assert_called_once()
            call_args, _ = mock_run.call_args
            cmd = list(call_args[0])
            assert "vim" in cmd, f"Expected vim in command: {cmd}"

            # Assert: the editor receives only the annotated diff path (no -d flag)
            assert annotated_path in cmd, (
                f"Expected {annotated_path} in command: {cmd}"
            )
            # Assert only one file path in the command (not two files)
            file_args = [a for a in cmd if isinstance(a, str) and a != "vim"]
            assert len(file_args) == 1, (
                f"Expected exactly 1 file argument, got {file_args}: {cmd}"
            )
            assert "-d" not in cmd, f"Expected no -d flag in command: {cmd}"

            # Assert: reconstruct_from_diff was called with the edited content
            mock_reconstruct.assert_called_once()

            # Assert: _setup_before_file was NOT called (no before file needed)
            mock_setup_before.assert_not_called()

            # Assert: returns True
            assert result is True, f"Expected True, got {result}"

            # Assert: action params updated if content changed
            assert "edits" in action.params, (
                "Expected 'edits' key in action.params"
            )

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
            assert any(isinstance(a, ConfirmScreen) for a in push_args), (
                "Should push ConfirmScreen for GUI editors"
            )

            # Assert: harvest_edit_diff was called after confirm
            mock_harvest.assert_called_once()

        # Assert: before file was deleted
        app._system_env.delete_file.assert_called_with(before_path)
