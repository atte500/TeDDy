"""Tests for the background editor flow (Wiring: Console).

Verifies that typing 'e' in the ask loop calls _launch_editor_background
instead of _open_editor_blocking, and that the harvest path returns content.
"""

import os
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


class TestRealLaunchEditorBackground:
    """Tests for the REAL background editor implementation (subprocess.Popen + TTY + persistent file)."""

    PROD_PREFIX = "teddy_executor.adapters.outbound.console_interactor_ask_loop"

    @pytest.fixture
    def real_ask_loop(self, mock_system_env, mock_tooling):
        """Create a ConsoleAskLoop with real dependencies (no mock overrides on the method itself)."""
        return ConsoleAskLoop(mock_system_env, mock_tooling)

    def test_launch_editor_background_creates_file_and_sets_path(self, real_ask_loop, tmp_path):
        """_launch_editor_background should create a temp file with initial content, set _active_editor_path,
        call subprocess.Popen with TTY inheritance, and return an empty string."""
        # Override create_temp_file to return a known path inside tmp_path
        temp_file = str(tmp_path / "editor_content.md")
        real_ask_loop._system_env.create_temp_file.return_value = temp_file

        with (
            patch("subprocess.Popen", autospec=True) as mock_popen,
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.sys.stdin") as mock_stdin,
            patch(f"{self.PROD_PREFIX}.sys.stdout") as mock_stdout,
            patch(f"{self.PROD_PREFIX}.sys.stderr") as mock_stderr,
        ):
            prompt = "test prompt"
            result = real_ask_loop._launch_editor_background(prompt)

            # Method must return empty string (non-blocking)
            assert result == "", f"Expected empty string, got: {repr(result)}"

            # A temp file must have been created
            assert os.path.exists(temp_file), f"Temp file not created: {temp_file}"
            with open(temp_file, "r", encoding="utf-8") as f:
                content = f.read()
            # The file should contain the prompt and the marker
            assert "test prompt" in content, "Prompt not in file content"
            assert "Please enter your response above this line" in content, "Marker not in file content"

            # _active_editor_path must be set to the temp file path
            assert hasattr(real_ask_loop, "_active_editor_path"), "Instance missing _active_editor_path"
            assert real_ask_loop._active_editor_path == temp_file, f"Expected '{temp_file}', got '{real_ask_loop._active_editor_path}'"

            # subprocess.Popen must have been called with the editor command and the temp file path
            mock_popen.assert_called_once()
            call_args, call_kwargs = mock_popen.call_args
            cmd = call_args[0] if isinstance(call_args[0], list) else call_args[0]
            assert temp_file in cmd, f"Temp file path not in command: {cmd}"
            # Verify TTY inheritance: stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr
            assert call_kwargs.get("stdin") is mock_stdin, "stdin not inherited"
            assert call_kwargs.get("stdout") is mock_stdout, "stdout not inherited"
            assert call_kwargs.get("stderr") is mock_stderr, "stderr not inherited"
