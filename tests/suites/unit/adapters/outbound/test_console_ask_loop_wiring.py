"""Wiring tests: End-to-end editor flow through ConsoleAskLoop.run().

Verifies the full integration path for both CLI and GUI editors:
- CLI editor: subprocess.run is called, content is returned directly.
- GUI editor: subprocess.Popen is called, empty string returned,
  and harvest on Enter via _handle_empty_input returns content.
"""

from unittest.mock import MagicMock, patch

import pytest

import os
import tempfile

from teddy_executor.adapters.outbound.console_interactor_ask_loop import (
    ConsoleAskLoop,
)


@pytest.fixture
def mock_system_env():
    env = MagicMock()
    env.create_temp_file.return_value = os.path.join(
        tempfile.gettempdir(), "fake_wiring.md"
    )
    return env


@pytest.fixture
def mock_tooling():
    tooling = MagicMock()
    return tooling


class TestWiringEndToEndEditorFlow:
    """End-to-end wiring tests for the editor loop.

    These tests exercise the full run() loop with the real
    _launch_editor_background, _flush_stdin, _is_cli_editor,
    and _handle_empty_input implementations. Only the subprocess
    calls and prompt_toolkit input are mocked.
    """

    PROD_PREFIX = "teddy_executor.adapters.outbound.console_interactor_ask_loop"

    @pytest.fixture
    def ask_loop(self, mock_system_env, mock_tooling):
        return ConsoleAskLoop(mock_system_env, mock_tooling)

    def test_wiring_cli_editor_returns_content_directly(
        self, ask_loop, mock_tooling, tmp_path
    ):
        """When the editor is a CLI editor, _launch_editor_background
        uses subprocess.run synchronously and returns harvested content.
        The run() loop returns that content immediately without going
        into harvest mode."""

        # Arrange: set up a known temp path
        temp_file = str(tmp_path / "wiring_cli.md")
        ask_loop._system_env.create_temp_file.return_value = temp_file

        # Arrange: CLI editor classification
        mock_tooling.find_editor.return_value = ["/usr/bin/vim"]

        expected_content = "Wiring test content from vim"

        def write_content(*args, **kwargs):
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(expected_content)

        # Arrange: user types 'e' once, then loop returns content
        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", return_value="e"),
            patch("subprocess.run", side_effect=write_content),
        ):
            # Act
            result = ask_loop.run("wiring prompt")

        # Assert: the harvested content is returned directly
        assert result == expected_content, (
            f"Expected '{expected_content}', got {repr(result)}"
        )

        # Assert: the temp file was cleaned up (_active_editor_path is None)
        assert ask_loop._active_editor_path is None, (
            f"Expected None, got {ask_loop._active_editor_path}"
        )

    def test_wiring_gui_editor_returns_empty_then_harvests_on_enter(
        self, ask_loop, mock_tooling, tmp_path
    ):
        """When the editor is a GUI editor, _launch_editor_background
        uses subprocess.Popen and returns empty string. The run() loop
        continues, and when the user presses Enter, the harvest path
        (_handle_empty_input) reads and returns the file content."""

        # Arrange: set up a known temp path
        temp_file = str(tmp_path / "wiring_gui.md")
        ask_loop._system_env.create_temp_file.return_value = temp_file

        # Arrange: GUI editor classification
        mock_tooling.find_editor.return_value = ["code", "--wait"]

        # Content that the GUI editor would write to the file
        harvested_content = "Wiring test content from code"

        # ptk_prompt sequence: first 'e', then Enter to harvest
        prompt_sequence = iter(["e", ""])

        # We need to write content to the file before harvest.
        # Mock subprocess.Popen to write the content (simulating editor save).
        def write_gui_content(*args, **kwargs):
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(harvested_content)

        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(
                f"{self.PROD_PREFIX}.ptk_prompt",
                side_effect=lambda *a, **kw: next(prompt_sequence),
            ),
            patch("subprocess.Popen", side_effect=write_gui_content),
        ):
            # Act
            result = ask_loop.run("wiring prompt")

        # Assert: finally, the harvested content is returned
        assert result == harvested_content, (
            f"Expected '{harvested_content}', got {repr(result)}"
        )

        # Assert: the file was cleaned up
        assert ask_loop._active_editor_path is None, (
            f"Expected None, got {ask_loop._active_editor_path}"
        )
