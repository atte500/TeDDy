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


def test_get_prompt_retrieves_default_prompt_from_root(mock_clipboard, tmp_path):
    """
    Scenario 1 (Revised): Get a default prompt from the root prompts folder.
    - Given: A /prompts/architect.md file exists at the project root.
    - And: The command is run from a subdirectory.
    - When: The user runs `teddy get-prompt architect`.
    - Then: The content of the root prompt file is printed, regardless of extension.
    """
    # Setup root prompt with a .md extension to test extension-agnostic logic
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "architect.md").write_text("dummy root prompt content")

    # Use a .git folder as the project root sentinel
    (tmp_path / ".git").mkdir()

    # Setup subdirectory to run from
    subdir = tmp_path / "some" / "subdir"
    subdir.mkdir(parents=True)

    with runner.isolated_filesystem(temp_dir=subdir):
        result = runner.invoke(app, ["get-prompt", "architect"])

    assert result.exit_code == 0
    assert "dummy root prompt content" in result.stdout
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


def test_get_prompt_fails_for_non_existent_prompt(mock_clipboard):
    """
    Scenario 3: Attempt to get a non-existent prompt
    - Given: No prompt named 'non-existent' exists.
    - When: The user runs `teddy get-prompt non-existent`.
    - Then: An error message is printed to stderr.
    - And: The command exits with a non-zero status code.
    """
    result = runner.invoke(app, ["get-prompt", "non-existent-prompt"])

    assert result.exit_code != 0
    assert "Prompt 'non-existent-prompt' not found." in result.stderr
