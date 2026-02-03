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
def test_context_command_suppresses_copy_with_flag(mock_pyperclip: MagicMock):
    """
    Scenario 2: Clipboard behavior is suppressed with a flag
    -   Given a user or script needs to prevent clipboard interaction
    -   When they run a command with the suppression flag `teddy context --no-copy`
    -   Then the command's primary output is printed to standard output
    -   But the system clipboard is not modified
    -   And no clipboard-related confirmation message is printed.
    """
    # Arrange
    # The mock_pyperclip is already arranged by the decorator.

    # Act
    result = runner.invoke(app, ["context", "--no-copy"], catch_exceptions=False)

    # Assert
    assert result.exit_code == 0
    assert "System Information" in result.stdout
    assert "Context Vault" in result.stdout

    mock_pyperclip.copy.assert_not_called()
    assert "Output copied to clipboard." not in result.stdout


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
