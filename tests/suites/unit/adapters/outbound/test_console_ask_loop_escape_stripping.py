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
        """When user types 'e' with OSC sequences prepended, the OSC is
        stripped and the remaining 'e' launches the editor synchronously."""
        # The OSC payload is prepended to 'e', so after stripping we get 'e'.
        osc_payload = "\x1b]10;rgb:8080/8989/b3b3\x1b\\e"
        editor_content = "Actual work from vim"
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", return_value=osc_payload),
            patch.object(ask_loop, "_flush_stdin"),
            patch.object(ask_loop, "_open_editor_blocking", return_value=editor_content),
        ):
            result = ask_loop.run("test prompt")
            # The OSC must be stripped, and the stripped 'e' launches editor.
            assert "8080/8989" not in result, (
                f"OSC payload leaked into result: {repr(result)}"
            )
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
            patch.object(ask_loop, "_open_editor_blocking", return_value=editor_content),
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
            patch.object(ask_loop, "_open_editor_blocking", return_value=""),
        ):
            result = ask_loop.run("test prompt")
            assert result == "my response", (
                f"Expected follow-up text, got: {repr(result)}"
            )

    def test_strips_osc_when_typing_normal_text(self, ask_loop):
        """Escape sequences are stripped unconditionally from normal input."""
        osc_payload = "\x1b]10;rgb:8080/8989/b3b3\x1b\\test"
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", return_value=osc_payload),
            patch.object(ask_loop, "_flush_stdin"),
        ):
            result = ask_loop.run("test prompt")
            assert "\x1b]" not in result, (
                f"Escape sequences leaked: {repr(result)}"
            )
            assert result == "test", (
                f"Expected 'test', got: {repr(result)}"
            )

    def test_ansi_sgr_stripped_from_normal_input(self, ask_loop):
        """ANSI SGR codes are stripped unconditionally."""
        ansi_text = "\x1b[31mred\x1b[0mtext"
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", return_value=ansi_text),
            patch.object(ask_loop, "_flush_stdin"),
        ):
            result = ask_loop.run("test prompt")
            assert result == "redtext", (
                f"Expected 'redtext', got: {repr(result)}"
            )

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
