from unittest.mock import MagicMock
from tests.setup.test_environment import TestEnvironment
from tests.drivers.cli_adapter import CliTestAdapter
from tests.drivers.plan_builder import MarkdownPlanBuilder


def setup_clipboard_mock(monkeypatch):
    mock_pyperclip = MagicMock()
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.cli_helpers.pyperclip", mock_pyperclip
    )
    return mock_pyperclip


def test_context_command_copies_to_clipboard_by_default(tmp_path, monkeypatch):
    """Scenario: context command copies its output to the clipboard by default."""
    TestEnvironment(monkeypatch, tmp_path).setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    mock_pyperclip = setup_clipboard_mock(monkeypatch)

    (tmp_path / "README.md").write_text("Hello World", encoding="utf-8")

    result = adapter.run_cli_command(["context"])

    assert result.exit_code == 0
    assert "Hello World" in result.stdout
    mock_pyperclip.copy.assert_called_once()
    assert "Output copied to clipboard." in result.stderr


def test_context_command_suppresses_copy_with_flag(tmp_path, monkeypatch):
    """Scenario: context command does not copy output when --no-copy flag is present."""
    TestEnvironment(monkeypatch, tmp_path).setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    mock_pyperclip = setup_clipboard_mock(monkeypatch)

    result = adapter.run_cli_command(["context", "--no-copy"])

    assert result.exit_code == 0
    mock_pyperclip.copy.assert_not_called()
    assert "Output copied to clipboard." not in result.stderr


def test_execute_command_copies_to_clipboard_by_default(tmp_path, monkeypatch):
    """Scenario: execute command copies its final report to the clipboard by default."""
    TestEnvironment(monkeypatch, tmp_path).setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    mock_pyperclip = setup_clipboard_mock(monkeypatch)

    plan = MarkdownPlanBuilder("Clipboard").add_create("hello.txt", "Hello!").build()

    # We use run_cli_command to test DEFAULT behavior (not suppressing copy)
    result = adapter.run_cli_command(["execute", "--plan-content", plan, "-y"])

    assert result.exit_code == 0
    assert "Execution report copied to clipboard." in result.stderr
    mock_pyperclip.copy.assert_called_once()
    assert "# Execution Report: Clipboard" in mock_pyperclip.copy.call_args[0][0]


def test_execute_command_suppresses_copy_with_flag(tmp_path, monkeypatch):
    """Scenario: execute command does not copy report when --no-copy flag is present."""
    TestEnvironment(monkeypatch, tmp_path).setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    mock_pyperclip = setup_clipboard_mock(monkeypatch)

    plan = MarkdownPlanBuilder("No-Copy").add_create("hello.txt", "Hello!").build()

    result = adapter.run_cli_command(
        ["execute", "--plan-content", plan, "--no-copy", "-y"]
    )

    assert result.exit_code == 0
    mock_pyperclip.copy.assert_not_called()
    assert "Execution report copied to clipboard." not in result.stderr
