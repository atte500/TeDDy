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

    def test_launch_editor_background_creates_file_and_sets_path(
        self, real_ask_loop, tmp_path
    ):
        """_launch_editor_background should create a temp file with initial content, set _active_editor_path,
        and return an empty string (the editor launch is deferred to later deliverable)."""
        # Override create_temp_file to return a known path inside tmp_path
        temp_file = str(tmp_path / "editor_content.md")
        real_ask_loop._system_env.create_temp_file.return_value = temp_file

        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ConsoleAskLoop._flush_stdin"),
            patch("subprocess.run"),
        ):
            prompt = "test prompt"
            result = real_ask_loop._launch_editor_background(prompt)

            # Method returns empty string because the harvested content is empty
            # (only marker/prompt content, stripped to nothing before the marker)
            assert result == "", f"Expected empty string, got: {repr(result)}"

            # For a CLI editor, the file is cleaned up after harvesting,
            # so _active_editor_path is reset to None.
            assert hasattr(real_ask_loop, "_active_editor_path"), (
                "Instance missing _active_editor_path"
            )
            assert real_ask_loop._active_editor_path is None, (
                f"Expected None, got: {real_ask_loop._active_editor_path}"
            )

    def test_pty_plumbing_removed(self, ask_loop):
        """PTY plumbing must be removed: no _pty_master_fd, _pty_drainer_thread,
        _pty_drainer(), _launch_editor_in_pty(), _close_pty_master(), or cleanup()."""
        assert not hasattr(ask_loop, "_pty_master_fd"), (
            "_pty_master_fd should not exist"
        )
        assert not hasattr(ask_loop, "_pty_drainer_thread"), (
            "_pty_drainer_thread should not exist"
        )
        assert not hasattr(ask_loop, "_pty_drainer"), "_pty_drainer should not exist"
        assert not hasattr(ask_loop, "_launch_editor_in_pty"), (
            "_launch_editor_in_pty should not exist"
        )
        assert not hasattr(ask_loop, "_close_pty_master"), (
            "_close_pty_master should not exist"
        )
        assert not hasattr(ask_loop, "cleanup"), "cleanup should not exist"

    def test_stripped_osc_tail_is_cleared_and_harvest_runs(
        self, ask_loop, mock_system_env
    ):
        """Regression test for Bug #27: stripped OSC tail `]10;rgb:...` should
        be stripped by the hardened regex, making the input empty, which routes
        to `_handle_empty_input` -> harvest path returns file content.

        The fix combines:
        - Hardened regex matching stripped OSC tails (no \\x1b prefix)
        - Flush after editor launch in run()
        - Flush after subprocess spawn in _launch_editor_background()
        - Flush before file read in _handle_empty_input()
        """
        from unittest.mock import mock_open

        ask_loop._active_editor_path = "/tmp/editor_bug27.md"
        marker = "<!-- Please enter your response above this line. -->"
        file_content = "Bug fix content\n\n" + marker + "\n\nPrompt text"
        tail_input = "]10;rgb:8080/8989/b3b3"

        call_count = [0]

        def mock_pt(prompt_text):
            call_count[0] += 1
            if call_count[0] == 1:
                return tail_input
            return "fallback"

        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch.object(ask_loop, "_pt_prompt", side_effect=mock_pt),
            patch.object(ask_loop, "_launch_editor_background", return_value=""),
            patch("builtins.open", mock_open(read_data=file_content)),
        ):
            result = ask_loop.run("test prompt")

        assert "8080/8989" not in result, f"OSC tail leaked into result: {repr(result)}"
        assert result == "Bug fix content", (
            f"Expected harvested content 'Bug fix content', got {repr(result)}"
        )


class TestSynchronousCliEditorLaunch:
    """Tests for the synchronous CLI editor path of _launch_editor_background.

    When the resolved editor is a known terminal/CLI editor (vim, nano, etc.),
    _launch_editor_background should call subprocess.run synchronously, then
    read and return the file content.
    """

    PROD_PREFIX = "teddy_executor.adapters.outbound.console_interactor_ask_loop"

    @pytest.fixture
    def real_ask_loop(self, mock_system_env, mock_tooling):
        """Create a ConsoleAskLoop with real dependencies (no mock overrides on the method itself)."""
        return ConsoleAskLoop(mock_system_env, mock_tooling)

    def test_sync_cli_editor_creates_file_and_returns_content(
        self, real_ask_loop, tmp_path
    ):
        """For a CLI editor (vim), _launch_editor_background should create a temp file,
        call subprocess.run with the editor command and temp path, then read and return
        the harvested content."""

        # Arrange: set up a known temp file path
        temp_file = str(tmp_path / "editor_content.md")
        real_ask_loop._system_env.create_temp_file.return_value = temp_file

        # Arrange: set up mock_tooling to return a CLI editor
        real_ask_loop._tooling.find_editor.return_value = ["/usr/bin/vim"]

        # Expected content that the editor would write
        expected_content = "User typed this in vim"

        # Define a side_effect that writes expected content to the temp file.
        # This simulates the editor saving and exiting after subprocess.run is called.
        def write_editor_content(*args, **kwargs):
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(expected_content)

        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch("subprocess.run", side_effect=write_editor_content) as mock_run,
        ):
            # Act
            result = real_ask_loop._launch_editor_background("test prompt")

            # Assert: subprocess.run was called with the editor command + temp path
            mock_run.assert_called_once()
            call_args, _ = mock_run.call_args
            cmd = call_args[0] if isinstance(call_args[0], list) else list(call_args[0])
            assert temp_file in cmd, f"Temp file path not in command: {cmd}"
            assert "/usr/bin/vim" in cmd, f"Vim not in command: {cmd}"

        # Assert: returned content is the harvested file content
        assert result == expected_content, (
            f"Expected '{expected_content}', got {repr(result)}"
        )

    def test_sync_cli_editor_reuses_persistent_file(self, real_ask_loop, tmp_path):
        """When _active_editor_path is already set, a CLI editor should update the file,
        call subprocess.run, and return the updated content."""

        # Arrange: set up a persistent file path
        temp_file = str(tmp_path / "persistent_editor.md")
        real_ask_loop._active_editor_path = temp_file

        # Arrange: write initial content (simulating previous edit)
        marker = "<!-- Please enter your response above this line. -->"
        initial_content = f"\n\n{marker}\n\nOld prompt"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(initial_content)

        # Arrange: set up mock_tooling to return a CLI editor
        real_ask_loop._tooling.find_editor.return_value = ["/usr/bin/vim"]

        # Updated content that the editor would produce
        updated_content = "Updated from vim"

        # Define a side_effect that writes updated content to the temp file
        def write_updated_content(*args, **kwargs):
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(updated_content)

        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch("subprocess.run", side_effect=write_updated_content) as mock_run,
        ):
            # Act
            result = real_ask_loop._launch_editor_background("new prompt")

            # Assert: subprocess.run was called
            mock_run.assert_called_once()
            call_args, _ = mock_run.call_args
            cmd = call_args[0] if isinstance(call_args[0], list) else list(call_args[0])
            assert temp_file in cmd, f"Temp file path not in command: {cmd}"

        # Assert: returned content is the updated file content
        assert result == updated_content, (
            f"Expected '{updated_content}', got {repr(result)}"
        )


class TestGuiEditorLaunchPreservation:
    """Tests for the GUI editor path of _launch_editor_background.

    When the resolved editor is a known GUI editor (code, sublime, cursor, etc.),
    _launch_editor_background should call subprocess.Popen and return "" so the
    interactive loop continues with the harvest-on-Enter pattern.
    """

    PROD_PREFIX = "teddy_executor.adapters.outbound.console_interactor_ask_loop"

    @pytest.fixture
    def real_ask_loop(self, mock_system_env, mock_tooling):
        """Create a ConsoleAskLoop with real dependencies."""
        return ConsoleAskLoop(mock_system_env, mock_tooling)

    def test_gui_editor_launches_popen_and_returns_empty_string(
        self, real_ask_loop, tmp_path
    ):
        """For a GUI editor (code), _launch_editor_background should call subprocess.Popen
        with the editor command and temp path, then return "" to continue the loop."""

        # Arrange: set up a known temp file path
        temp_file = str(tmp_path / "editor_gui.md")
        real_ask_loop._system_env.create_temp_file.return_value = temp_file

        # Arrange: set up mock_tooling to return a GUI editor
        real_ask_loop._tooling.find_editor.return_value = ["/usr/local/bin/code", "-w"]

        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ConsoleAskLoop._flush_stdin"),
            patch("subprocess.Popen") as mock_popen,
        ):
            # Act
            result = real_ask_loop._launch_editor_background("test prompt")

            # Assert: subprocess.Popen was called with the editor command + temp path
            mock_popen.assert_called_once()
            call_args, _ = mock_popen.call_args
            cmd = call_args[0] if isinstance(call_args[0], list) else list(call_args[0])
            assert temp_file in cmd, f"Temp file path not in command: {cmd}"
            assert "/usr/local/bin/code" in cmd, f"Code not in command: {cmd}"

        # Assert: returned content is empty string (loop continues)
        assert result == "", f"Expected empty string, got: {repr(result)}"

        # Assert: _active_editor_path is preserved for later harvest
        assert real_ask_loop._active_editor_path == temp_file, (
            f"Expected '{temp_file}', got '{real_ask_loop._active_editor_path}'"
        )

    def test_gui_editor_reuses_persistent_file(self, real_ask_loop, tmp_path):
        """When _active_editor_path is already set, a GUI editor should update the file,
        call subprocess.Popen, and return "" preserving the path for harvest."""

        # Arrange: set up a persistent file path
        temp_file = str(tmp_path / "persistent_gui.md")
        real_ask_loop._active_editor_path = temp_file

        # Arrange: write initial content (simulating previous edit)
        marker = "<!-- Please enter your response above this line. -->"
        initial_content = f"\n\n{marker}\n\nOld prompt"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(initial_content)

        # Arrange: set up mock_tooling to return a GUI editor
        real_ask_loop._tooling.find_editor.return_value = ["code"]

        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ConsoleAskLoop._flush_stdin"),
            patch("subprocess.Popen") as mock_popen,
        ):
            # Act
            result = real_ask_loop._launch_editor_background("new prompt")

            # Assert: subprocess.Popen was called
            mock_popen.assert_called_once()
            call_args, _ = mock_popen.call_args
            cmd = call_args[0] if isinstance(call_args[0], list) else list(call_args[0])
            assert temp_file in cmd, f"Temp file path not in command: {cmd}"

        # Assert: returned content is empty string (loop continues)
        assert result == "", f"Expected empty string, got: {repr(result)}"

        # Assert: _active_editor_path is preserved
        assert real_ask_loop._active_editor_path == temp_file, (
            f"Expected '{temp_file}', got '{real_ask_loop._active_editor_path}'"
        )
