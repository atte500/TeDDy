import pytest

from teddy_executor.adapters.outbound.console_interactor import (
    ConsoleInteractorAdapter,
)
from teddy_executor.core.domain.models.plan import ActionData


class TestConsoleInteractorAdapter:
    @pytest.fixture
    def adapter(self) -> ConsoleInteractorAdapter:
        return ConsoleInteractorAdapter()

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
