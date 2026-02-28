import pytest

from teddy_executor.adapters.outbound.console_interactor import (
    ConsoleInteractorAdapter,
)
from teddy_executor.core.domain.models.plan import ActionData


class TestConsoleInteractorAdapter:
    @pytest.fixture
    def adapter(self) -> ConsoleInteractorAdapter:
        return ConsoleInteractorAdapter()

    def test_ask_question_standard_input_single_line(
        self, adapter: ConsoleInteractorAdapter, monkeypatch
    ):
        """Test that ask_question reads exactly one line of standard input if 'e' is not typed."""
        # The user just types their response and hits Enter.
        inputs = iter(["My standard response"])
        monkeypatch.setattr("builtins.input", lambda: next(inputs))

        response = adapter.ask_question("What say you?")
        assert response == "My standard response"

    def test_ask_question_opens_editor_on_e(
        self, adapter: ConsoleInteractorAdapter, monkeypatch, tmp_path
    ):
        """Test that typing 'e' opens an editor, reads the temp file, and strips comments."""
        import subprocess
        from unittest.mock import MagicMock
        from pathlib import Path

        inputs = iter(["e"])
        monkeypatch.setattr("builtins.input", lambda: next(inputs))

        # We need to mock subprocess.run to intercept the editor launch and write to the temp file
        mock_run = MagicMock()
        file_content_before_editor = ""

        def mock_subprocess_run(cmd, *args, **kwargs):
            nonlocal file_content_before_editor
            mock_run(cmd, *args, **kwargs)
            # cmd is e.g. ["mock_editor", "/tmp/path/to/file.md"]
            filepath = Path(cmd[-1])
            file_content_before_editor = filepath.read_text(encoding="utf-8")
            filepath.write_text(
                "Hello from editor\n\n--- Please enter your response above this line. Save and close this file to submit. ---\n\nDon't read this.",
                encoding="utf-8",
            )

        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
        monkeypatch.setenv("EDITOR", "mock_editor")

        prompt_text = "AI says: Write a lot:"
        response = adapter.ask_question(prompt_text)

        assert "Hello from editor" == response.strip()
        assert "Don't read this." not in response
        assert mock_run.called
        assert mock_run.call_args[0][0][0] == "mock_editor"
        # Assert the prompt was written below the marker in the initial file content
        assert (
            file_content_before_editor
            == f"\n\n--- Please enter your response above this line. Save and close this file to submit. ---\n\n{prompt_text}\n"
        )

    def test_ask_question_editor_fallback_when_no_editor_found(
        self, adapter: ConsoleInteractorAdapter, monkeypatch
    ):
        import shutil

        inputs = iter(["e", "Fallback input", ""])
        monkeypatch.setattr("builtins.input", lambda: next(inputs))

        # Ensure no editor is found
        monkeypatch.delenv("VISUAL", raising=False)
        monkeypatch.delenv("EDITOR", raising=False)
        monkeypatch.setattr(shutil, "which", lambda cmd: None)

        response = adapter.ask_question("Prompt:")
        assert response == "Fallback input"

    def test_ask_question_editor_fails_returns_empty(
        self, adapter: ConsoleInteractorAdapter, monkeypatch
    ):
        import subprocess

        inputs = iter(["e"])
        monkeypatch.setattr("builtins.input", lambda: next(inputs))
        monkeypatch.setenv("EDITOR", "mock_editor")

        def mock_subprocess_run(cmd, *args, **kwargs):
            raise subprocess.CalledProcessError(1, cmd)

        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

        response = adapter.ask_question("Prompt:")
        assert response == ""

    def test_confirm_action_approves_on_y(
        self, adapter: ConsoleInteractorAdapter, monkeypatch
    ):
        """Test that 'y' input approves the action."""
        # Arrange
        monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: "y")

        # Act
        dummy_action = ActionData(type="test", params={})
        approved, reason = adapter.confirm_action(
            action=dummy_action, action_prompt="Perform the action?"
        )

        # Assert
        assert approved is True
        assert reason == ""
        # Prompting logic is now handled by typer.prompt and not asserted here.

    def test_confirm_action_denies_on_n_and_captures_reason(
        self, adapter: ConsoleInteractorAdapter, monkeypatch
    ):
        """Test that 'n' input denies and captures a reason."""
        # Arrange
        inputs = iter(["n", "User denied."])
        monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: next(inputs))

        # Act
        dummy_action = ActionData(type="test", params={})
        approved, reason = adapter.confirm_action(
            action=dummy_action, action_prompt="Do it?"
        )

        # Assert
        assert approved is False
        assert reason == "User denied."

        # Assert that both prompts were shown, regardless of other writes
        # Prompting logic is now handled by typer.prompt and not asserted here.

    def test_confirm_action_handles_eof_error(
        self, adapter: ConsoleInteractorAdapter, monkeypatch
    ):
        """Test that an EOFError results in a denial."""

        # Arrange
        from typer import Abort

        def raise_abort(*args, **kwargs):
            raise Abort()

        monkeypatch.setattr("typer.prompt", raise_abort)

        # Act
        dummy_action = ActionData(type="test", params={})
        approved, reason = adapter.confirm_action(
            action=dummy_action, action_prompt="Another action?"
        )

        # Assert
        assert approved is False
        assert reason == "Skipped due to non-interactive session."
        # Prompting logic is now handled by typer.prompt and not asserted here.

    def test_notify_skipped_action_prints_warning(
        self, adapter: ConsoleInteractorAdapter, monkeypatch
    ):
        """Test that a skipped action prints a warning to stderr."""
        import typer
        from unittest.mock import MagicMock

        mock_secho = MagicMock()
        monkeypatch.setattr(typer, "secho", mock_secho)

        dummy_action = ActionData(type="TEST_ACTION", params={})
        reason = "A test skip reason"

        adapter.notify_skipped_action(dummy_action, reason)

        mock_secho.assert_called_once_with(
            f"[SKIPPED] TEST_ACTION: {reason}",
            fg=typer.colors.YELLOW,
            err=True,
        )
