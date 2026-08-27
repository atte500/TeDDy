"""Regression tests for ConsoleAskLoop escape sequence stripping (Bug #25).

Verifies that terminal escape sequences (OSC/ANSI) are stripped from user
input when a background editor is active, preventing leaks like
']10;rgb:8080/8989/b3b3' from appearing in the returned response.
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
    """Tests for the _strip_escape_sequences fix."""

    PROD_PREFIX = "teddy_executor.adapters.outbound.console_interactor_ask_loop"

    def test_strips_osc_sequence_when_editor_active(self, ask_loop):
        """When active editor path is set and ptk returns an OSC sequence,
        the final returned string must have the sequence stripped."""
        osc_payload = "\x1b]10;rgb:8080/8989/b3b3\x1b\\"
        # _pt_prompt returns the OSC sequence as user input
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", return_value=osc_payload),
            patch.object(ask_loop, "_flush_stdin"),  # silence flush
            patch.object(ask_loop, "_launch_editor_background"),
        ):
            # Simulate that an editor is already active
            ask_loop._active_editor_path = "/tmp/fake_editor.md"
            result = ask_loop.run("test prompt")
            assert "8080/8989" not in result, (
                f"OSC payload leaked into result: {repr(result)}"
            )
            assert result == "", (
                f"Expected empty string (only OSC present), got: {repr(result)}"
            )

    def test_strips_osc_with_bel_terminator(self, ask_loop):
        """OSC sequences terminated with BEL (\\x07) must also be stripped."""
        osc_bel = "\x1b]10;rgb:8080/8989/b3b3\x07"
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", return_value=osc_bel),
            patch.object(ask_loop, "_flush_stdin"),
            patch.object(ask_loop, "_launch_editor_background"),
        ):
            ask_loop._active_editor_path = "/tmp/fake_editor.md"
            result = ask_loop.run("test prompt")
            assert "8080/8989" not in result, f"OSC payload leaked: {repr(result)}"

    def test_preserves_normal_text_when_editor_active(self, ask_loop):
        """Normal user input (no escape sequences) must be preserved unchanged
        when the editor is active."""
        normal_text = "Hello, this is my response!"
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", return_value=normal_text),
            patch.object(ask_loop, "_flush_stdin"),
            patch.object(ask_loop, "_launch_editor_background"),
        ):
            ask_loop._active_editor_path = "/tmp/fake_editor.md"
            result = ask_loop.run("test prompt")
            assert result == "Hello, this is my response!", (
                f"Normal text was modified: {repr(result)}"
            )

    def test_does_not_strip_when_editor_not_active(self, ask_loop):
        """When no editor is active, escape sequences in input must be
        returned as-is (the stripping is only applied after editor opens)."""
        # This guards against accidental over-stripping of normal input.
        osc_payload = "\x1b]10;rgb:8080/8989/b3b3\x1b\\test"
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", side_effect=[osc_payload]),
            patch.object(ask_loop, "_flush_stdin"),
            patch.object(ask_loop, "_launch_editor_background"),
        ):
            # Ensure no active editor
            ask_loop._active_editor_path = None
            result = ask_loop.run("test prompt")
            # Without stripping, the OSC sequence is preserved
            assert "\x1b]" in result, (
                "Escape sequences should NOT be stripped when no editor is active"
            )

    def test_strip_osc_and_uses_editor_content(self, ask_loop):
        """When OSC leaks into stdin but the editor file contains the user's
        message, the OSC is stripped and the editor content is returned."""
        osc_payload = "\x1b]10;rgb:8080/8989/b3b3\x1b\\"
        editor_content = "My actual message written in vim"
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", return_value=osc_payload),
            patch.object(ask_loop, "_flush_stdin"),
            patch.object(ask_loop, "_launch_editor_background"),
            patch.object(ask_loop, "_read_editor_result", return_value=editor_content),
        ):
            ask_loop._active_editor_path = "/tmp/fake_editor.md"
            result = ask_loop.run("test prompt")
            # OSC must be stripped, editor content must be returned
            assert "8080/8989" not in result, (
                f"OSC payload leaked into result: {repr(result)}"
            )
            assert result == "My actual message written in vim", (
                f"Expected editor content, got: {repr(result)}"
            )

    def test_strip_osc_and_returns_empty_when_editor_empty(self, ask_loop):
        """When OSC leaks and the editor file is empty, the response is
        empty (user pressed Enter without writing anything)."""
        osc_payload = "\x1b]10;rgb:8080/8989/b3b3\x1b\\"
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", return_value=osc_payload),
            patch.object(ask_loop, "_flush_stdin"),
            patch.object(ask_loop, "_launch_editor_background"),
            patch.object(ask_loop, "_read_editor_result", return_value=""),
        ):
            ask_loop._active_editor_path = "/tmp/fake_editor.md"
            result = ask_loop.run("test prompt")
            assert "8080/8989" not in result, (
                f"OSC payload leaked: {repr(result)}"
            )
            assert result == "", (
                f"Expected empty string when editor empty, got: {repr(result)}"
            )

    def test_ansi_sgr_stripped_when_editor_active(self, ask_loop):
        """ANSI SGR codes (e.g., \\x1b[31m) must also be stripped."""
        ansi_text = "\x1b[31mred\x1b[0mtext"
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", return_value=ansi_text),
            patch.object(ask_loop, "_flush_stdin"),
            patch.object(ask_loop, "_launch_editor_background"),
        ):
            ask_loop._active_editor_path = "/tmp/fake_editor.md"
            result = ask_loop.run("test prompt")
            # ANSI codes should be stripped, leaving only visible characters
            assert "red" in result and "text" in result, (
                f"Expected 'redtext', got: {repr(result)}"
            )
            assert "\x1b[" not in result, f"ANSI codes still present: {repr(result)}"
