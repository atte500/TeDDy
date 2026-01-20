from pathlib import Path
from typer.testing import CliRunner
from teddy_executor.main import app
import pytest

runner = CliRunner(mix_stderr=False)


@pytest.fixture
def mock_clipboard(monkeypatch):
    """Mocks pyperclip.copy to avoid clipboard side effects during tests."""

    def mock_copy(x: str) -> None:
        pass

    monkeypatch.setattr("pyperclip.copy", mock_copy)


def test_get_prompt_retrieves_default_prompt(mock_clipboard):
    """
    Scenario 1: Get a default prompt
    - Given: No local prompt overrides exist.
    - When: The user runs `teddy get-prompt architect`.
    - Then: The content of the default `architect.xml` prompt is printed.
    - And: A confirmation message indicates the output has been copied.
    """
    result = runner.invoke(app, ["get-prompt", "architect"])

    assert result.exit_code == 0
    assert "Default architect prompt content" in result.stdout
    # The confirmation message is printed to stderr
    assert "Output copied to clipboard." in result.stderr


def test_get_prompt_retrieves_local_override_prompt(mock_clipboard, tmp_path):
    """
    Scenario 2: Get a locally overridden prompt
    - Given: A file exists at `.teddy/prompts/architect.md`.
    - When: The user runs `teddy get-prompt architect` from that directory.
    - Then: The content of the local file is printed.
    """
    # Run command from the temp directory, creating files inside it
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Setup local prompt override inside the CWD
        prompt_dir = Path.cwd() / ".teddy" / "prompts"
        prompt_dir.mkdir(parents=True)
        (prompt_dir / "architect.md").write_text("local override content")

        result = runner.invoke(app, ["get-prompt", "architect"])

    assert result.exit_code == 0
    assert "local override content" in result.stdout
