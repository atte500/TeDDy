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
    _launch_editor_background, _flush_stdin, and _handle_empty_input
    implementations plus the shared editor classifier. Only the subprocess
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


class TestWiringLauncherSuffixClassification:
    """A terminal editor resolved to a Windows launcher wrapper must take the
    synchronous CLI path, not the fire-and-forget GUI path. Otherwise the ask
    loop returns control to the prompt while the editor still owns the terminal.
    """

    PROD_PREFIX = "teddy_executor.adapters.outbound.console_interactor_ask_loop"

    @pytest.fixture
    def ask_loop(self, mock_system_env, mock_tooling):
        return ConsoleAskLoop(mock_system_env, mock_tooling)

    @pytest.mark.parametrize(
        "wrapped_editor",
        [
            pytest.param("/usr/bin/nvim.CMD", id="upper-cmd"),
            pytest.param("/usr/bin/vim.BAT", id="upper-bat"),
            pytest.param("/usr/bin/nano.EXE", id="upper-exe"),
        ],
    )
    def test_launcher_wrapper_takes_synchronous_path(
        self, ask_loop, mock_tooling, tmp_path, wrapped_editor
    ):
        temp_file = str(tmp_path / "wrapper.md")
        ask_loop._system_env.create_temp_file.return_value = temp_file
        mock_tooling.find_editor.return_value = [wrapped_editor]

        expected_content = "Wrapper content from the terminal editor"

        def write_content(*args, **kwargs):
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(expected_content)

        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch("subprocess.run", side_effect=write_content) as mock_run,
            patch("subprocess.Popen") as mock_popen,
        ):
            result = ask_loop._launch_editor_background("wiring prompt")

        assert result == expected_content, (
            f"Expected '{expected_content}', got {repr(result)}"
        )
        mock_run.assert_called_once()
        mock_popen.assert_not_called()


class TestWiringTerminalReplyDiscardsDraft:
    """A terminal reply abandons the opened editor draft.

    The session shares one ask-loop instance across turns. A draft that
    survives the reply pins the next turn to the "Editor opened" prompt and
    leaves the temp file on disk.
    """

    PROD_PREFIX = "teddy_executor.adapters.outbound.console_interactor_ask_loop"

    @pytest.fixture
    def draft_loop(self, mock_system_env, mock_tooling, tmp_path):
        draft_path = str(tmp_path / "abandoned_draft.md")
        mock_system_env.create_temp_file.return_value = draft_path

        def _delete(path: str) -> None:
            if os.path.exists(path):
                os.remove(path)

        mock_system_env.delete_file.side_effect = _delete
        mock_tooling.find_editor.return_value = ["code", "--wait"]
        return ConsoleAskLoop(mock_system_env, mock_tooling), draft_path

    def _editor_side_effect(self, draft_path):
        def _save(*_args, **_kwargs):
            with open(draft_path, "w", encoding="utf-8") as handle:
                handle.write("unsaved draft")

        return _save

    def test_terminal_reply_deletes_the_abandoned_draft(self, draft_loop):
        ask_loop, draft_path = draft_loop
        replies = iter(["e", "terminal answer"])

        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(
                f"{self.PROD_PREFIX}.ptk_prompt",
                side_effect=lambda *_a, **_k: next(replies),
            ),
            patch("subprocess.Popen", side_effect=self._editor_side_effect(draft_path)),
            patch.object(ask_loop, "_flush_stdin"),
        ):
            result = ask_loop.run("turn one prompt")

        assert result == "terminal answer"
        assert ask_loop._active_editor_path is None
        assert not os.path.exists(draft_path)

    def test_next_turn_renders_the_fresh_editor_prompt(self, draft_loop):
        ask_loop, draft_path = draft_loop
        rendered: list[str] = []
        replies = iter(["e", "turn one answer", "turn two answer"])

        def _reply(prompt_text, **_kwargs):
            rendered.append(prompt_text)
            return next(replies)

        with (
            patch(f"{self.PROD_PREFIX}.sys.stdin.isatty", return_value=True),
            patch(f"{self.PROD_PREFIX}.ptk_prompt", side_effect=_reply),
            patch("subprocess.Popen", side_effect=self._editor_side_effect(draft_path)),
            patch.object(ask_loop, "_flush_stdin"),
        ):
            assert ask_loop.run("turn one prompt") == "turn one answer"
            assert ask_loop.run("turn two prompt") == "turn two answer"

        assert rendered[2] == "Response (type 'e' for editor) › "
        assert ask_loop._active_editor_path is None
