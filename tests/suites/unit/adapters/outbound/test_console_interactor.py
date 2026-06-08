import pytest
from tests.harness.setup.mocking import POSIXPathMock

from teddy_executor.adapters.outbound.console_interactor import (
    ConsoleInteractorAdapter,
)
from teddy_executor.core.domain.models.plan import ActionData


class TestConsoleInteractorAdapter:
    @pytest.fixture
    def adapter(self, mock_env, tmp_path) -> ConsoleInteractorAdapter:
        # Specialized setup for this adapter's tests
        mock_env.create_temp_file.side_effect = lambda suffix="": str(
            tmp_path / f"temp_file{suffix}"
        )
        mock_config = POSIXPathMock()
        mock_config.get_setting.return_value = None
        return ConsoleInteractorAdapter(system_env=mock_env, config_service=mock_config)

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
        self, adapter: ConsoleInteractorAdapter, mock_env, monkeypatch
    ):
        """Test that typing 'e' opens an editor, reads the temp file, and strips comments."""
        from pathlib import Path

        # Input 'e' to launch, then empty Enter to read result
        inputs = iter(["e", ""])
        monkeypatch.setattr("builtins.input", lambda: next(inputs))

        file_content_before_editor = ""

        def mock_run_command(cmd, *_args, **_kwargs):
            nonlocal file_content_before_editor
            filepath = Path(cmd[-1])
            file_content_before_editor = filepath.read_text(encoding="utf-8")
            filepath.write_text(
                "Hello from editor\n\n<!-- Please enter your response above this line. -->\n\nDon't read this.",
                encoding="utf-8",
            )

        mock_env.run_command.side_effect = mock_run_command
        mock_env.get_env.side_effect = lambda key: (
            "mock_editor" if key == "EDITOR" else None
        )
        mock_env.which.return_value = "/usr/bin/mock_editor"

        prompt_text = "AI says: Write a lot:"
        response = adapter.ask_question(prompt_text)

        assert "Hello from editor" == response.strip()
        assert "Don't read this." not in response
        assert mock_env.run_command.called
        # Assert the prompt was written below the marker in the initial file content
        assert (
            file_content_before_editor
            == f"\n\n<!-- Please enter your response above this line. -->\n\n{prompt_text}\n"
        )

    def test_ask_question_editor_fallback_when_no_editor_found(
        self, adapter: ConsoleInteractorAdapter, mock_env, monkeypatch
    ):
        inputs = iter(["e", "Fallback input", ""])
        monkeypatch.setattr("builtins.input", lambda: next(inputs))

        # Ensure no editor is found via port
        mock_env.get_env.return_value = None
        mock_env.which.return_value = None

        response = adapter.ask_question("Prompt:")
        assert response == "Fallback input"

    def test_ask_question_editor_fails_returns_empty(
        self, adapter: ConsoleInteractorAdapter, mock_env, monkeypatch
    ):
        # Input 'e' (fails), then "" (tries to read result but none exists), then "" (confirms empty response)
        inputs = iter(["e", "", ""])
        monkeypatch.setattr("builtins.input", lambda: next(inputs))
        mock_env.get_env.return_value = "mock_editor"
        mock_env.which.return_value = "/usr/bin/mock_editor"

        mock_env.run_command.side_effect = Exception("Editor failed")

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

    def test_confirm_action_denies_on_n_and_immediately_skips(
        self, adapter: ConsoleInteractorAdapter, monkeypatch
    ):
        """Test that 'n' input denies and skips immediately without prompting for reason."""
        # Arrange
        inputs = iter(["n"])
        monkeypatch.setattr("typer.prompt", lambda *_args, **_kwargs: next(inputs))

        # Act
        dummy_action = ActionData(type="test", params={})
        approved, reason = adapter.confirm_action(
            action=dummy_action, action_prompt="Do it?"
        )

        # Assert
        assert approved is False
        assert reason == ""

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
        from tests.harness.setup.mocking import POSIXPathMock

        mock_secho = POSIXPathMock()
        monkeypatch.setattr(typer, "secho", mock_secho)

        dummy_action = ActionData(type="TEST_ACTION", params={})
        reason = "A test skip reason"

        adapter.notify_skipped_action(dummy_action, reason)

        mock_secho.assert_called_once_with(
            f"[SKIPPED] TEST_ACTION: {reason}",
            fg=typer.colors.YELLOW,
            err=True,
        )

    def test_display_message_doubles_newlines(
        self, adapter: ConsoleInteractorAdapter, monkeypatch
    ):
        """Test that display_message applies double_newlines to the message content before printing."""
        from tests.harness.setup.mocking import POSIXPathMock

        # Arrange
        mock_print = POSIXPathMock()
        monkeypatch.setattr(adapter._console, "print", mock_print)

        # Act
        adapter.display_message("line1\nline2")

        # Assert — currently fails because no transformation is applied
        mock_print.assert_called_once_with("line1\n\nline2")
