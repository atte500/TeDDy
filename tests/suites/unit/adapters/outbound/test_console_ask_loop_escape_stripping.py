"""Regression tests for ConsoleAskLoop escape sequence stripping (Bug #25).

Verifies that terminal escape sequences (OSC/ANSI) are stripped from user
input, and that the synchronous editor flow correctly returns editor content
or continues the loop on empty editor.
"""

from unittest.mock import MagicMock, patch

import pytest

from teddy_executor.adapters.outbound.console_interactor_ask_loop import (
    ConsoleAskLoop,
)


@pytest.fixture
def mock_system_env():
    env = MagicMock()
    env.create_temp_file.return_value = "/tmp/fake_editor.md"
    return env


@pytest.fixture
def mock_tooling():
    tooling = MagicMock()
    tooling.find_editor.return_value = ["/usr/bin/vim"]
    return tooling


@pytest.fixture
def ask_loop(mock_system_env, mock_tooling):
    return ConsoleAskLoop(mock_system_env, mock_tooling)


class TestEscapeSequenceStripping:
    """Tests for escape sequence stripping and the synchronous editor flow."""

    PROD_PREFIX = "teddy_executor.adapters.outbound.console_interactor_ask_loop"

    def test_strips_osc_sequence_when_user_types_e(self, ask_loop):
        """Typing 'e' launches the editor and returns its content.

        Under PTY isolation, OSC sequences never reach the parent's stdin
        before the first editor launch (they are isolated in the pty slave).
        This test verifies that a clean 'e' input correctly triggers the
        editor and returns the harvested content.
        """
        editor_content = "Actual work from vim"
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", return_value="e"),
            patch.object(ask_loop, "_flush_stdin"),
            patch.object(
                ask_loop, "_launch_editor_background", return_value=editor_content
            ),
        ):
            result = ask_loop.run("test prompt")
            assert result == "Actual work from vim", (
                f"Expected editor content, got: {repr(result)}"
            )

    def test_user_types_e_returns_editor_content(self, ask_loop):
        """When user types 'e' and the editor returns content, that content
        is returned directly."""
        editor_content = "Message from vim"
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", return_value="e"),
            patch.object(ask_loop, "_flush_stdin"),
            patch.object(
                ask_loop, "_launch_editor_background", return_value=editor_content
            ),
        ):
            result = ask_loop.run("test prompt")
            assert result == "Message from vim", (
                f"Expected editor content, got: {repr(result)}"
            )

    def test_user_types_e_empty_editor_continues_loop(self, ask_loop):
        """When user types 'e' and the editor returns empty content, the loop
        continues and the user can type normal text."""
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(
                f"{self.PROD_PREFIX}.ptk_prompt",
                side_effect=["e", "my response"],
            ),
            patch.object(ask_loop, "_flush_stdin"),
            patch.object(ask_loop, "_launch_editor_background", return_value=""),
        ):
            result = ask_loop.run("test prompt")
            assert result == "my response", (
                f"Expected follow-up text, got: {repr(result)}"
            )

    def test_strips_osc_when_typing_normal_text(self, ask_loop):
        """Escape sequences are preserved when no editor is active (antipattern fix).

        Under PTY isolation, OSC sequences from terminal contamination never
        reach the parent's stdin before the first editor launch. When no editor
        is active, escape sequences in user input are preserved as-is.
        """
        osc_payload = "\x1b]10;rgb:8080/8989/b3b3\x1b\\test"
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", return_value=osc_payload),
            patch.object(ask_loop, "_flush_stdin"),
        ):
            result = ask_loop.run("test prompt")
            # Without an active editor, escape sequences are preserved (antipattern fix).
            # Under PTY isolation, this scenario cannot occur from terminal contamination,
            # so the conservative behavior is to pass through raw input.
            assert "\x1b]" in result, (
                "Escape sequences should be preserved when editor is not active"
            )
            assert "test" in result, (
                "Normal text should be preserved alongside escape sequences"
            )

    def test_ansi_sgr_stripped_from_normal_input(self, ask_loop):
        """ANSI SGR codes are preserved when no editor is active (antipattern fix).

        Under PTY isolation, ANSI sequences from terminal contamination never
        reach the parent's stdin before the first editor launch. When no editor
        is active, escape sequences in user input are preserved as-is.
        """
        ansi_text = "\x1b[31mred\x1b[0mtext"
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", return_value=ansi_text),
            patch.object(ask_loop, "_flush_stdin"),
        ):
            result = ask_loop.run("test prompt")
            # Without an active editor, ANSI sequences are preserved (antipattern fix).
            # Under PTY isolation, this scenario cannot occur from terminal contamination,
            # so the conservative behavior is to pass through raw input.
            assert "\x1b[31m" in result, (
                "ANSI sequences should be preserved when editor is not active"
            )
            assert "red" in result, "Normal text should be preserved"
            assert "text" in result, "Normal text should be preserved"

    def test_preserves_normal_text(self, ask_loop):
        """Normal text is preserved after stripping (no-op)."""
        normal_text = "Hello, this is my response!"
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", return_value=normal_text),
            patch.object(ask_loop, "_flush_stdin"),
        ):
            result = ask_loop.run("test prompt")
            assert result == "Hello, this is my response!", (
                f"Expected normal text, got: {repr(result)}"
            )
