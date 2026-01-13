from unittest.mock import MagicMock

import pytest

from teddy_executor.adapters.outbound.console_interactor import (
    ConsoleInteractorAdapter,
)


class TestConsoleInteractorAdapter:
    @pytest.fixture
    def adapter(self) -> ConsoleInteractorAdapter:
        return ConsoleInteractorAdapter()

    def test_confirm_action_approves_on_y(
        self, adapter: ConsoleInteractorAdapter, monkeypatch
    ):
        """Test that 'y' input approves the action."""
        # Arrange
        monkeypatch.setattr("builtins.input", lambda: "y")
        mock_stderr = MagicMock()
        monkeypatch.setattr("sys.stderr", mock_stderr)

        # Act
        approved, reason = adapter.confirm_action("Perform the action?")

        # Assert
        assert approved is True
        assert reason == ""
        mock_stderr.write.assert_any_call("Perform the action?\nApprove? (y/n): ")

    def test_confirm_action_denies_on_n_and_captures_reason(
        self, adapter: ConsoleInteractorAdapter, monkeypatch
    ):
        """Test that 'n' input denies and captures a reason."""
        # Arrange
        inputs = iter(["n", "User denied."])
        monkeypatch.setattr("builtins.input", lambda: next(inputs))
        mock_stderr = MagicMock()
        monkeypatch.setattr("sys.stderr", mock_stderr)

        # Act
        approved, reason = adapter.confirm_action("Do it?")

        # Assert
        assert approved is False
        assert reason == "User denied."

        # Assert that both prompts were shown, regardless of other writes
        mock_stderr.write.assert_any_call("Do it?\nApprove? (y/n): ")
        mock_stderr.write.assert_any_call("Reason for skipping (optional): ")

    def test_confirm_action_handles_eof_error(
        self, adapter: ConsoleInteractorAdapter, monkeypatch
    ):
        """Test that an EOFError results in a denial."""

        # Arrange
        def raise_eof(*args):
            raise EOFError

        monkeypatch.setattr("builtins.input", raise_eof)
        mock_stderr = MagicMock()
        monkeypatch.setattr("sys.stderr", mock_stderr)

        # Act
        approved, reason = adapter.confirm_action("Another action?")

        # Assert
        assert approved is False
        assert reason == "Skipped due to non-interactive session."
        mock_stderr.write.assert_any_call("Another action?\nApprove? (y/n): ")
