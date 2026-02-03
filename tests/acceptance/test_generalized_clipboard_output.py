from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from teddy_executor.main import app
from typer.testing import CliRunner

from .helpers import run_cli_command

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
    # The mock_pyperclip is already arranged by the decorator.

    # Act
    result = runner.invoke(app, ["context"], catch_exceptions=False)

    # Assert
    assert result.exit_code == 0
    assert "System Information" in result.stdout
    assert "Context Vault" in result.stdout

    mock_pyperclip.copy.assert_called_once()
    # Ensure the content copied is the same as what was printed to stdout
    confirmation_message = "Output copied to clipboard."
    assert confirmation_message in result.stderr

    expected_content_to_copy = result.stdout.strip()
    mock_pyperclip.copy.assert_called_with(expected_content_to_copy)


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
    assert confirmation_message not in result.stderr


@patch("teddy_executor.main.pyperclip", new_callable=MagicMock)
def test_execute_command_copies_to_clipboard_by_default(
    mock_pyperclip: MagicMock, monkeypatch, tmp_path: Path
):
    """
    Verify the execute command copies its report to the clipboard by default.
    """
    # Arrange
    plan_content = {
        "actions": [
            {
                "action": "create_file",
                "path": "hello.txt",
                "content": "Hello, World!",
            }
        ]
    }
    plan_file = tmp_path / "plan.yml"
    plan_file.write_text(yaml.dump(plan_content))
    args = ["execute", str(plan_file), "--yes"]

    # Act
    result = run_cli_command(monkeypatch, args, cwd=tmp_path)

    # Assert
    assert result.exit_code == 0
    assert "Execution report copied to clipboard." in result.stderr
    mock_pyperclip.copy.assert_called_once()
    assert "status: SUCCESS" in mock_pyperclip.copy.call_args[0][0]


@patch("teddy_executor.main.pyperclip", new_callable=MagicMock)
def test_execute_command_suppresses_copy_with_flag(
    mock_pyperclip: MagicMock, monkeypatch, tmp_path: Path
):
    """
    Verify the execute command does not copy with the --no-copy flag.
    """
    # Arrange
    plan_content = {
        "actions": [
            {
                "action": "create_file",
                "path": "hello.txt",
                "content": "Hello, World!",
            }
        ]
    }
    plan_file = tmp_path / "plan.yml"
    plan_file.write_text(yaml.dump(plan_content))
    args = ["execute", str(plan_file), "--yes", "--no-copy"]

    # Act
    result = run_cli_command(monkeypatch, args, cwd=tmp_path)

    # Assert
    assert result.exit_code == 0
    assert "Execution report copied to clipboard." not in result.stderr
    mock_pyperclip.copy.assert_not_called()
