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
        monkeypatch.setattr(
            "teddy_executor.adapters.outbound.console_interactor_ask_loop.ptk_prompt",
            lambda msg, **kwargs: next(inputs),
        )
        monkeypatch.setattr(
            "teddy_executor.adapters.outbound.console_interactor_ask_loop.ConsoleAskLoop._is_tty",
            lambda self: True,
        )

        response = adapter.ask_question("What say you?")
        assert response == "My standard response"

    def test_ask_question_opens_editor_on_e(
        self, adapter: ConsoleInteractorAdapter, mock_env, monkeypatch
    ):
        """Test that typing 'e' opens the background editor and returns its content."""
        # Input 'e' to launch editor, then empty Enter to read result
        inputs = iter(["e", ""])
        monkeypatch.setattr(
            "teddy_executor.adapters.outbound.console_interactor_ask_loop.ptk_prompt",
            lambda msg, **kwargs: next(inputs),
        )
        monkeypatch.setattr(
            "teddy_executor.adapters.outbound.console_interactor_ask_loop.ConsoleAskLoop._is_tty",
            lambda self: True,
        )
        monkeypatch.setattr(
            "teddy_executor.adapters.outbound.console_interactor_ask_loop.ConsoleAskLoop._launch_editor_background",
            lambda self, prompt: "Hello from editor",
        )

        response = adapter.ask_question("AI says: Write a lot:")
        assert "Hello from editor" == response.strip()

    def test_ask_question_editor_fallback_when_no_editor_found(
        self, adapter: ConsoleInteractorAdapter, mock_env, monkeypatch
    ):
        inputs = iter(["e", "Fallback input", ""])
        monkeypatch.setattr(
            "teddy_executor.adapters.outbound.console_interactor_ask_loop.ptk_prompt",
            lambda msg, **kwargs: next(inputs),
        )
        monkeypatch.setattr(
            "teddy_executor.adapters.outbound.console_interactor_ask_loop.ConsoleAskLoop._is_tty",
            lambda self: True,
        )
        # Mock the background editor to return empty (simulating no content/failure)
        # so the loop continues and the user's manual input is used.
        monkeypatch.setattr(
            "teddy_executor.adapters.outbound.console_interactor_ask_loop.ConsoleAskLoop._launch_editor_background",
            lambda self, prompt: "",
        )

        response = adapter.ask_question("Prompt:")
        assert response == "Fallback input"

    def test_ask_question_editor_fails_returns_empty(
        self, adapter: ConsoleInteractorAdapter, mock_env, monkeypatch
    ):
        # Input 'e' (simulated empty editor), then "" (confirms empty response)
        inputs = iter(["e", "", ""])
        monkeypatch.setattr(
            "teddy_executor.adapters.outbound.console_interactor_ask_loop.ptk_prompt",
            lambda msg, **kwargs: next(inputs),
        )
        monkeypatch.setattr(
            "teddy_executor.adapters.outbound.console_interactor_ask_loop.ConsoleAskLoop._is_tty",
            lambda self: True,
        )
        # Mock the background editor to return empty (simulating failure)
        monkeypatch.setattr(
            "teddy_executor.adapters.outbound.console_interactor_ask_loop.ConsoleAskLoop._launch_editor_background",
            lambda self, prompt: "",
        )

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

    def test_display_message_preserves_newlines(
        self, adapter: ConsoleInteractorAdapter, monkeypatch
    ):
        """Test that display_message preserves newlines as-is (no transformation anywhere in pipeline)."""
        from tests.harness.setup.mocking import POSIXPathMock

        # Arrange
        mock_print = POSIXPathMock()
        monkeypatch.setattr(adapter._console, "print", mock_print)

        # Act
        adapter.display_message("line1\nline2")

        # Assert — display_message is a transparent pass-through
        mock_print.assert_called_once_with("line1\nline2")
