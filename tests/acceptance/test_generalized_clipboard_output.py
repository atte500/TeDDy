from pathlib import Path
from unittest.mock import MagicMock, patch

from teddy_executor.main import app
from typer.testing import CliRunner

from .helpers import run_cli_command, parse_markdown_report

runner = CliRunner()


@patch("teddy_executor.main.pyperclip", new_callable=MagicMock)
def test_context_command_copies_to_clipboard_by_default(mock_pyperclip: MagicMock):
    """
    Scenario 1: `context` command defaults to copying output
    -   Given a user is in an interactive terminal session
    -   When they run the command `teddy context`
    -   Then the full project context is printed to standard output
    -   And the full project context is also copied to the system clipboard
    -   And a confirmation message (e.g., "Output copied to clipboard.") is printed.
    """
    # Arrange
    confirmation_message = "Output copied to clipboard."

    # Run in an isolated filesystem to avoid reading the project's own source code,
    # which would cause the confirmation message string inside this test file
    # to appear in the output and break the split logic.
    with runner.isolated_filesystem():
        # Create a dummy file to have some context. We use README.md because
        # the default context gatherer looks for it.
        Path("README.md").write_text("Hello World", encoding="utf-8")

        # Act
        result = runner.invoke(app, ["context"], catch_exceptions=False)

        # Assert
        assert result.exit_code == 0
        assert "System Information" in result.stdout
        assert "Hello World" in result.stdout

        mock_pyperclip.copy.assert_called_once()
        # Ensure the confirmation message is present
        assert confirmation_message in result.stderr

        # The content copied to the clipboard is everything *before* the confirmation message.
        # We use rsplit to ensure we split on the *last* occurrence (the actual message),
        # just in case the string appeared in the file content.
        expected_content_from_stdout = result.stdout.rsplit(confirmation_message, 1)[0]

        # We compare stripped content to avoid issues with trailing newlines added by echo vs copy.
        actual_copied_content = mock_pyperclip.copy.call_args[0][0]
        assert actual_copied_content.strip() == expected_content_from_stdout.strip()


@patch("teddy_executor.main.pyperclip", new_callable=MagicMock)
@patch("teddy_executor.main.container")
def test_context_command_suppresses_copy_with_flag(
    mock_container: MagicMock, mock_pyperclip: MagicMock
):
    """
    Scenario 2: Clipboard behavior is suppressed with a flag.
    This test mocks the context service to prevent the test's assertion string from
    colliding with the content of the files being printed.
    """
    # Arrange
    from teddy_executor.core.domain.models import ContextResult
    from teddy_executor.core.ports.inbound.get_context_use_case import (
        IGetContextUseCase,
    )

    mock_context_service = MagicMock(spec=IGetContextUseCase)
    mock_context_service.get_context.return_value = ContextResult(
        system_info={}, repo_tree="", context_vault_paths=[], file_contents={}
    )
    mock_container.resolve.return_value = mock_context_service

    confirmation_message = "Output copied to clipboard."

    # Act
    result = runner.invoke(app, ["context", "--no-copy"], catch_exceptions=False)

    # Assert
    assert result.exit_code == 0
    mock_pyperclip.copy.assert_not_called()

    # With --no-copy, the message should not appear in EITHER stream
    assert confirmation_message not in result.stdout


@patch("teddy_executor.main.pyperclip", new_callable=MagicMock)
def test_execute_command_copies_to_clipboard_by_default(
    mock_pyperclip: MagicMock, monkeypatch, tmp_path: Path
):
    """
    Verify the execute command copies its report to the clipboard by default.
    """
    # Arrange
    from .plan_builder import MarkdownPlanBuilder

    builder = MarkdownPlanBuilder("Test Clipboard Output")
    builder.add_action(
        "CREATE",
        params={
            "File Path": "[hello.txt](/hello.txt)",
            "Description": "Test file.",
        },
        content_blocks={"": ("text", "Hello, World!")},
    )
    plan_content = builder.build()
    args = ["execute", "--plan-content", plan_content, "--yes"]

    # Act
    result = run_cli_command(monkeypatch, args, cwd=tmp_path)

    # Assert
    assert result.exit_code == 0
    assert "Execution report copied to clipboard." in result.stderr
    mock_pyperclip.copy.assert_called_once()

    # Parse the stdout to get the canonical report dict
    report_dict = parse_markdown_report(result.stdout)
    # The actual copied content might have slightly different whitespace,
    # so we parse it too and compare the dictionaries for robustness.
    actual_copied_dict = parse_markdown_report(mock_pyperclip.copy.call_args[0][0])
    assert report_dict == actual_copied_dict


@patch("teddy_executor.main.pyperclip", new_callable=MagicMock)
def test_execute_command_suppresses_copy_with_flag(
    mock_pyperclip: MagicMock, monkeypatch, tmp_path: Path
):
    """
    Verify the execute command does not copy with the --no-copy flag.
    """
    # Arrange
    from .plan_builder import MarkdownPlanBuilder

    builder = MarkdownPlanBuilder("Test No-Copy Flag")
    builder.add_action(
        "CREATE",
        params={
            "File Path": "[hello.txt](/hello.txt)",
            "Description": "Test file.",
        },
        content_blocks={"": ("text", "Hello, World!")},
    )
    plan_content = builder.build()
    args = ["execute", "--plan-content", plan_content, "--yes", "--no-copy"]

    # Act
    result = run_cli_command(monkeypatch, args, cwd=tmp_path)

    # Assert
    assert result.exit_code == 0
    assert "Execution report copied to clipboard." not in result.stdout
    mock_pyperclip.copy.assert_not_called()
