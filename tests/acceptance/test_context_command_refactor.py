from pathlib import Path

from tests.acceptance.helpers import run_cli_command


def test_context_creates_default_perm_context_file(tmp_path: Path, monkeypatch):
    """
    Scenario 2: Simplified Default Configuration
    Given a project that does not have a .teddy/project.context file
    When the user runs the `teddy context` command for the first time
    Then a new file .teddy/project.context MUST be created.
    And its content MUST ONLY contain README.md and docs/ARCHITECTURE.md.
    """
    # Arrange
    (tmp_path / "README.md").touch()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/ARCHITECTURE.md").touch()

    # Act
    result = run_cli_command(monkeypatch, ["context"], cwd=tmp_path)

    # Assert
    assert result.exit_code == 0
    teddy_dir = tmp_path / ".teddy"

    # Check project.context
    perm_context_file = teddy_dir / "project.context"
    assert perm_context_file.exists()
    expected_content = "README.md\ndocs/ARCHITECTURE.md\n"
    assert perm_context_file.read_text() == expected_content

    # Check .gitignore
    gitignore_file = teddy_dir / ".gitignore"
    assert gitignore_file.exists()
    assert gitignore_file.read_text() == "*"


def test_context_generates_standard_output_and_is_clean(tmp_path: Path, monkeypatch):
    """
    Scenario 1: Standardized Output Format
    Scenario 3: Clean Context Vault Listing
    Scenario 4: Direct Repository Tree Output
    Also tests that missing files are reported.
    """
    # Arrange
    (tmp_path / ".teddy").mkdir()
    (tmp_path / ".teddy/project.context").write_text(
        "README.md\nnon_existent_file.md\n", encoding="utf-8"
    )
    (tmp_path / ".teddy/temp.context").write_text(
        "docs/ARCHITECTURE.md\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("# Test README", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/ARCHITECTURE.md").write_text(
        "# Test Architecture", encoding="utf-8"
    )

    # Act
    result = run_cli_command(monkeypatch, ["context"], cwd=tmp_path)
    output = result.stdout

    # Assert
    assert result.exit_code == 0
    assert "# System Information" in output
    assert "shell:" in output
    assert "# Repository Tree" in output
    assert "# Test README" in output
    assert "[docs/ARCHITECTURE.md](/docs/ARCHITECTURE.md)" in output
    assert "# Test Architecture" in output
    assert "non_existent_file.md" in output
    assert "--- FILE NOT FOUND ---" in output

    # Assert - Direct Repository Tree Output (Scenario 4)
    assert not (tmp_path / "repotree.txt").exists()


def test_context_uses_dynamic_language_fences(tmp_path: Path, monkeypatch):
    """
    Given a project with files of different extensions
    When the user runs the `teddy context` command
    Then the generated markdown payload MUST use dynamic language tags for the code fences.
    """
    # Arrange
    (tmp_path / ".teddy").mkdir()
    (tmp_path / ".teddy/project.context").write_text(
        "main.py\nconfig.cfg\n", encoding="utf-8"
    )
    (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "config.cfg").write_text("debug=true", encoding="utf-8")

    # Act
    result = run_cli_command(monkeypatch, ["context"], cwd=tmp_path)
    output = result.stdout

    # Assert
    assert result.exit_code == 0
    assert "```py\nprint('hello')\n```" in output
    assert "```cfg\ndebug=true\n```" in output
