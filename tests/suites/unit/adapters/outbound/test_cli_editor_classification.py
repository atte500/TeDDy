"""Tests for CLI editor classification (Deliverable 2).

Verifies that _is_cli_editor correctly identifies terminal editors
(vim, nvim, nano, etc.) vs. GUI editors (code, sublime, cursor, etc.).
"""

from teddy_executor.adapters.outbound.console_interactor_ask_loop import (
    ConsoleAskLoop,
)


class TestCliEditorClassification:
    """Tests for _is_cli_editor static method."""

    def test_returns_true_for_known_terminal_editors(self):
        """Known terminal editors should be classified as CLI editors."""
        terminal_editors = [
            ["/usr/bin/vim"],
            ["nvim"],
            ["vi"],
            ["nano"],
            ["emacs"],
            ["pico"],
            ["helix"],
            ["hx"],
            ["kak"],
        ]
        for cmd in terminal_editors:
            assert ConsoleAskLoop._is_cli_editor(cmd), (
                f"Expected {cmd[0]} to be classified as CLI editor"
            )

    def test_returns_false_for_gui_editors(self):
        """GUI editors like code, sublime, cursor should be classified as GUI editors."""
        gui_editors = [
            ["code", "-r", "--wait"],
            ["subl"],
            ["sublime_text"],
            ["cursor"],
            ["notepad", "test.md"],
        ]
        for cmd in gui_editors:
            assert not ConsoleAskLoop._is_cli_editor(cmd), (
                f"Expected {cmd[0]} to be classified as GUI editor"
            )

    def test_returns_false_for_empty_or_unknown_editors(self):
        """Unknown editors should default to GUI/background behaviour (False)."""
        unknown = [
            [],
            None,
            ["/usr/local/bin/some_unknown_editor"],
            ["my-own-editor"],
        ]
        for cmd in unknown:
            assert not ConsoleAskLoop._is_cli_editor(cmd), (
                f"Expected {cmd} to be classified as GUI editor"
            )

    def test_basename_extraction_works_with_full_paths(self):
        """Editor commands with full paths should use basename for classification."""
        path_editors = [
            "/usr/local/bin/nvim",
            "/snap/bin/vim",
            "/usr/bin/nano",
        ]
        for cmd in path_editors:
            assert ConsoleAskLoop._is_cli_editor([cmd]), (
                f"Expected {cmd} to be classified as CLI editor"
            )
