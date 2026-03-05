import os
from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_first_time_initialization_creates_teddy_directory_and_files(tmp_path):
    """
    Scenario: First-time initialization of the .teddy directory
    - Given a workspace without a .teddy/ directory.
    - When any teddy command (e.g., teddy context) is executed.
    - Then a .teddy/ directory MUST be created in the current working directory.
    - And it MUST contain a config.yaml file with the default template.
    - And it MUST contain an init.context file with the default template.
    """
    # Change current working directory to a fresh temporary directory
    os.chdir(tmp_path)

    # When
    result = runner.invoke(app, ["context", "--no-copy"])

    # Then
    assert result.exit_code == 0

    teddy_dir = tmp_path / ".teddy"
    config_file = teddy_dir / "config.yaml"
    init_context_file = teddy_dir / "init.context"

    assert teddy_dir.is_dir(), ".teddy directory should be created"
    assert config_file.is_file(), "config.yaml should be created"
    assert init_context_file.is_file(), "init.context should be created"

    # Verify default content of config.yaml
    config_content = config_file.read_text(encoding="utf-8")
    assert "TeDDy Configuration" in config_content
    assert "llm:" in config_content

    # Verify default content of init.context
    init_content = init_context_file.read_text(encoding="utf-8")
    assert "README.md" in init_content
    assert "docs/architecture/ARCHITECTURE.md" in init_content
