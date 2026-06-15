"""Unit tests for the console visibility helper functions in session_orchestrator.

These tests verify the contract (signatures and basic behavior) of:
- _print_initial_request
- _print_header_bar
- _print_user_message
"""

from unittest.mock import MagicMock, patch
from teddy_executor.core.services.session_orchestrator import (
    _print_initial_request,
    _print_header_bar,
    _print_user_message,
)


def test_helpers_import_and_call_without_error():
    """The three console visibility helpers should be importable and callable.

    This is the contract test: it asserts the functions exist and accept
    the expected arguments. It will fail with ImportError until the
    functions are implemented.
    """
    # _print_initial_request: (message: Optional[str], is_session: bool) -> None
    _print_initial_request(None, False)
    _print_initial_request("hello", True)
    _print_initial_request("  ", True)

    # _print_header_bar: (plan: Any, is_session: bool) -> None
    mock_plan = MagicMock()
    mock_plan.title = "Test"
    mock_plan.metadata = {"Status": "SUCCESS 🟢"}
    _print_header_bar(mock_plan, False)
    _print_header_bar(mock_plan, True)

    # _print_user_message: (message: Optional[str], is_session: bool) -> None
    _print_user_message(None, False)
    _print_user_message("user message", True)
    _print_user_message("  ", True)


# ---------------------------------------------------------------------------
# _print_initial_request
# ---------------------------------------------------------------------------


class TestPrintInitialRequest:
    """Tests for _print_initial_request."""

    def test_prints_nothing_when_not_session(self):
        """Should not print anything when is_session is False."""
        with patch(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            autospec=True,
        ) as mock_secho:
            _print_initial_request("hello", False)
        mock_secho.assert_not_called()

    def test_prints_nothing_when_message_none(self):
        """Should not print anything when message is None."""
        with patch(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            autospec=True,
        ) as mock_secho:
            _print_initial_request(None, True)
        mock_secho.assert_not_called()

    def test_prints_nothing_when_message_empty(self):
        """Should not print anything when message is empty."""
        with patch(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            autospec=True,
        ) as mock_secho:
            _print_initial_request("", True)
        mock_secho.assert_not_called()

    def test_prints_nothing_when_message_whitespace(self):
        """Should not print anything when message is whitespace-only."""
        with patch(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            autospec=True,
        ) as mock_secho:
            _print_initial_request("  ", True)
        mock_secho.assert_not_called()

    def test_prints_initial_request_with_message(self):
        """Should print 'Initial Request:' then the message, then blank line."""
        with patch(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            autospec=True,
        ) as mock_secho:
            _print_initial_request("hello world", True)

        assert mock_secho.call_count == 3
        mock_secho.assert_any_call("Initial Request:")
        mock_secho.assert_any_call("hello world")
        mock_secho.assert_any_call("")

    def test_strips_message_whitespace(self):
        """Should strip leading/trailing whitespace from the message."""
        with patch(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            autospec=True,
        ) as mock_secho:
            _print_initial_request("  hello world  ", True)

        mock_secho.assert_any_call("hello world")


# ---------------------------------------------------------------------------
# _print_header_bar
# ---------------------------------------------------------------------------


class TestPrintHeaderBar:
    """Tests for _print_header_bar."""

    def test_prints_nothing_when_not_session(self):
        """Should not print anything when is_session is False."""
        mock_plan = MagicMock()
        with patch(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            autospec=True,
        ) as mock_secho:
            _print_header_bar(mock_plan, False)
        mock_secho.assert_not_called()

    def test_prints_title_with_emoji(self):
        """Should print emoji and title when status has emoji."""
        mock_plan = MagicMock()
        mock_plan.title = "Implement safety limits"
        mock_plan.metadata = {"Status": "SUCCESS 🟢"}

        with patch(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            autospec=True,
        ) as mock_secho:
            _print_header_bar(mock_plan, True)

        mock_secho.assert_called_once_with("🟢 Implement safety limits")

    def test_prints_title_without_emoji_when_missing(self):
        """Should print title alone when status metadata is missing."""
        mock_plan = MagicMock()
        mock_plan.title = "My Plan"
        mock_plan.metadata = {}

        with patch(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            autospec=True,
        ) as mock_secho:
            _print_header_bar(mock_plan, True)

        mock_secho.assert_called_once_with("My Plan")

    def test_prints_emoji_alone_when_title_empty(self):
        """Should print emoji alone when title is empty."""
        mock_plan = MagicMock()
        mock_plan.title = ""
        mock_plan.metadata = {"Status": "FAILURE 🔴"}

        with patch(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            autospec=True,
        ) as mock_secho:
            _print_header_bar(mock_plan, True)

        mock_secho.assert_called_once_with("🔴")

    def test_prints_nothing_when_no_emoji_and_no_title(self):
        """Should print nothing when both emoji and title are missing."""
        mock_plan = MagicMock()
        mock_plan.title = ""
        mock_plan.metadata = {}

        with patch(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            autospec=True,
        ) as mock_secho:
            _print_header_bar(mock_plan, True)

        mock_secho.assert_not_called()

    def test_falls_back_to_lowercase_status_key(self):
        """Should check lowercase 'status' key if 'Status' is missing."""
        mock_plan = MagicMock()
        mock_plan.title = "Test"
        mock_plan.metadata = {"status": "SUCCESS 🟢"}

        with patch(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            autospec=True,
        ) as mock_secho:
            _print_header_bar(mock_plan, True)

        mock_secho.assert_called_once_with("🟢 Test")


# ---------------------------------------------------------------------------
# _print_user_message
# ---------------------------------------------------------------------------


class TestPrintUserMessage:
    """Tests for _print_user_message."""

    def test_prints_nothing_when_not_session(self):
        """Should not print anything when is_session is False."""
        with patch(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            autospec=True,
        ) as mock_secho:
            _print_user_message("hello", False)
        mock_secho.assert_not_called()

    def test_prints_nothing_when_message_none(self):
        """Should not print anything when message is None."""
        with patch(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            autospec=True,
        ) as mock_secho:
            _print_user_message(None, True)
        mock_secho.assert_not_called()

    def test_prints_nothing_when_message_empty(self):
        """Should not print anything when message is empty."""
        with patch(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            autospec=True,
        ) as mock_secho:
            _print_user_message("", True)
        mock_secho.assert_not_called()

    def test_prints_nothing_when_message_whitespace(self):
        """Should not print anything when message is whitespace-only."""
        with patch(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            autospec=True,
        ) as mock_secho:
            _print_user_message("  ", True)
        mock_secho.assert_not_called()

    def test_prints_user_message_with_content(self):
        """Should print blank line, 'User Message:', content, then trailing newline."""
        with patch(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            autospec=True,
        ) as mock_secho:
            _print_user_message("refactor this", True)

        assert mock_secho.call_count == 4
        mock_secho.assert_any_call("")  # blank line before
        mock_secho.assert_any_call("User Message:")
        mock_secho.assert_any_call("refactor this")
        mock_secho.assert_any_call("")  # trailing newline

    def test_strips_message_whitespace(self):
        """Should strip leading/trailing whitespace from the message."""
        with patch(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            autospec=True,
        ) as mock_secho:
            _print_user_message("  refactor this  ", True)

        mock_secho.assert_any_call("refactor this")
