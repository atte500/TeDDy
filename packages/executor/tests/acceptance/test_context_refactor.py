from pathlib import Path
from tests.acceptance.helpers import run_teddy_command


def test_context_command_uses_context_extension_and_ignores_gitignore_by_default(
    tmp_path: Path,
):
    """
    Feature: Context command uses .context files and ignores .gitignore by default.
    Scenario: The user runs the `context` command in a project.
    Given a project with a .gitignore file that ignores log files,
    And a file 'important.log' that is ignored by .gitignore,
    And a file 'source.py' that is not ignored,
    And a `.teddy/perm.context` file that explicitly includes both files,
    And an old `.teddy/config.txt` file that should be ignored,
    When the user runs `teddy context`,
    Then the output should contain the content of both 'important.log' and 'source.py',
    And the output should not mention 'config.txt'.
    """
    # Arrange: Create the project structure
    (tmp_path / ".gitignore").write_text("*.log\n")
    (tmp_path / "important.log").write_text("This is an important log.")
    (tmp_path / "source.py").write_text("print('hello world')")

    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    # Also ask for the repo tree to be included in the context
    (teddy_dir / "perm.context").write_text(
        "important.log\nsource.py\n.teddy/repotree.txt"
    )
    (teddy_dir / "config.txt").write_text(
        "this-file-should-not-be-read.txt"
    )  # Old format

    # Act: Run the context command
    result = run_teddy_command(["context"], cwd=tmp_path)

    # Assert
    assert result.returncode == 0
    stdout = result.stdout

    # Verify direct file access works and ignores .gitignore
    assert "--- File: important.log ---" in stdout
    assert "This is an important log." in stdout
    assert "--- File: source.py ---" in stdout
    assert "print('hello world')" in stdout

    # Verify that the generated repo tree ALSO ignores the .gitignore by default
    assert "--- File: .teddy/repotree.txt ---" in stdout
    assert "important.log" in stdout
    assert "source.py" in stdout

    # Verify that old .txt files are ignored
    assert "config.txt" not in stdout
    assert "this-file-should-not-be-read" not in stdout
