"""Tests for the background editor flow (Wiring: Console).

Verifies that typing 'e' in the ask loop calls _launch_editor_background
instead of _open_editor_blocking, and that the harvest path returns content.
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


class TestBackgroundEditorFlow:
    """Tests for the background+harvest editor pattern."""

    PROD_PREFIX = "teddy_executor.adapters.outbound.console_interactor_ask_loop"

    def test_e_launches_background_editor(self, ask_loop):
        """When user types 'e', _launch_editor_background is called instead of _open_editor_blocking."""
        editor_content = "Message from background vim"
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", return_value="e"),
            patch.object(ask_loop, "_flush_stdin"),
            patch.object(
                ask_loop, "_launch_editor_background", return_value=editor_content
            ),
        ):
            result = ask_loop.run("test prompt")
            assert result == "Message from background vim", (
                f"Expected editor content, got: {repr(result)}"
            )
            ask_loop._launch_editor_background.assert_called_once_with("test prompt")
