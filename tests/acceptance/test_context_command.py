from pathlib import Path
from tests.acceptance.helpers import run_teddy_command


def test_context_command_first_run(tmp_path: Path):
    """
    Scenario: First-time run in a new project
    Given I am in a project directory that does not contain a .teddy folder
    When I run the `teddy context` command
    Then a .teddy directory is created
    And a .teddy/.gitignore file is created containing the line `*`
    And a .teddy/context.json file is created
    And a .teddy/permanent_context.txt file is created
    And the .teddy/permanent_context.txt file contains default entries.
    """
    # Act
    result = run_teddy_command(args=["context"], cwd=tmp_path)

    # Assert
    assert result.returncode == 0, f"Teddy exited with an error:\n{result.stderr}"

    teddy_dir = tmp_path / ".teddy"
    assert teddy_dir.is_dir(), "The .teddy directory was not created."

    gitignore_file = teddy_dir / ".gitignore"
    assert gitignore_file.is_file(), ".teddy/.gitignore was not created."
    assert gitignore_file.read_text().strip() == "*", ".gitignore content is incorrect."

    context_json = teddy_dir / "context.json"
    assert context_json.is_file(), ".teddy/context.json was not created."

    permanent_context = teddy_dir / "permanent_context.txt"
    assert permanent_context.is_file(), ".teddy/permanent_context.txt was not created."

    # Check for default content in permanent_context.txt
    permanent_content = permanent_context.read_text()
    assert "README.md" in permanent_content
    assert "docs/ARCHITECTURE.md" in permanent_content
    assert "repotree.txt" in permanent_content
