"""
Regression test: MESSAGE action replies ARE printed to terminal during session mode.

This test verifies that:
1. MESSAGE action replies (stored in action_log.details) appear in terminal output
   even when plan.metadata["user_request"] is empty (Bug 16 guard).
2. Non-MESSAGE user messages still appear in terminal output (existing behavior preserved).
3. plan.metadata["user_request"] takes priority over action_logs when both are present.
4. Missing or empty action_logs are handled gracefully.
"""

from io import StringIO

import typer

from teddy_executor.core.services.session_orchestrator import _print_user_message


class TestPrintUserMessage:
    """Tests for the _print_user_message terminal output function."""

    def _capture_output(self, func, *args, **kwargs) -> str:
        """Capture typer.secho output and return as string."""
        captured = StringIO()

        def _secho(text: str = "", **kwargs) -> None:
            captured.write(text + "\n")

        original = typer.secho
        typer.secho = _secho  # type: ignore[assignment]
        try:
            func(*args, **kwargs)
        finally:
            typer.secho = original
        return captured.getvalue()

    def test_message_reply_printed_from_action_logs(self):
        """MESSAGE action reply should be printed when user_request is empty."""

        class MockPlan:
            metadata = {}  # No "user_request" key (Bug 16 scenario)

        class MockActionLog:
            action_type = "MESSAGE"
            details = "User reply: Yes, let's do it!"

        output = self._capture_output(
            _print_user_message,
            message=None,
            is_session=True,
            plan=MockPlan(),
            action_logs=[MockActionLog()],
        )
        assert "User reply: Yes, let's do it!" in output, (
            f"MESSAGE reply should appear in terminal output, got: {repr(output)}"
        )

    def test_non_message_user_request_still_printed(self):
        """Non-MESSAGE user_request should still be printed (existing behavior)."""

        class MockPlan:
            metadata = {"user_request": "User approved via m key"}

        output = self._capture_output(
            _print_user_message,
            message=None,
            is_session=True,
            plan=MockPlan(),
            action_logs=[],
        )
        assert "User approved via m key" in output, (
            f"user_request should appear in terminal output, got: {repr(output)}"
        )

    def test_user_request_prioritized_over_action_logs(self):
        """plan.metadata["user_request"] should take priority over action_logs."""

        class MockPlan:
            metadata = {"user_request": "User approved via m key"}

        class MockActionLog:
            action_type = "MESSAGE"
            details = "User reply: I think this is great!"

        output = self._capture_output(
            _print_user_message,
            message=None,
            is_session=True,
            plan=MockPlan(),
            action_logs=[MockActionLog()],
        )
        assert "User approved via m key" in output, (
            "user_request should appear in output"
        )
        assert "I think this is great!" not in output, (
            "MESSAGE reply should NOT appear when user_request is present"
        )

    def test_direct_message_parameter_used(self):
        """Direct message parameter should be used when provided."""
        output = self._capture_output(
            _print_user_message,
            message="Direct input from TUI m key",
            is_session=True,
            plan=None,
            action_logs=None,
        )
        assert "Direct input from TUI m key" in output, (
            f"Direct message should appear in terminal output, got: {repr(output)}"
        )

    def test_no_output_when_not_session(self):
        """No output should be printed when is_session=False."""
        output = self._capture_output(
            _print_user_message,
            message="Test message",
            is_session=False,
            plan=None,
            action_logs=None,
        )
        assert output == "", (
            f"No output should be printed for non-session mode, got: {repr(output)}"
        )

    def test_empty_message_no_output(self):
        """No output should be printed when message is empty and no fallbacks."""
        output = self._capture_output(
            _print_user_message,
            message=None,
            is_session=True,
            plan=None,
            action_logs=None,
        )
        assert output == "", (
            f"No output should be printed for empty message, got: {repr(output)}"
        )
