from typer.testing import CliRunner
from teddy_executor.main import app

runner = CliRunner(mix_stderr=False)


def test_get_prompt_retrieves_default_prompt(monkeypatch):
    """
    Scenario 1: Get a default prompt
    - Given: No local prompt overrides exist.
    - When: The user runs `teddy get-prompt architect`.
    - Then: The content of the default `architect.xml` prompt is printed.
    - And: A confirmation message indicates the output has been copied.
    """

    # Mock the clipboard copy function to avoid side effects
    def mock_copy(x: str) -> None:
        pass

    monkeypatch.setattr("pyperclip.copy", mock_copy)

    result = runner.invoke(app, ["get-prompt", "architect"])

    assert result.exit_code == 0
    assert "Default architect prompt content" in result.stdout
    # The confirmation message is printed to stderr
    assert "Output copied to clipboard." in result.stderr
