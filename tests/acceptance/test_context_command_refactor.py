import re
from pathlib import Path

from tests.acceptance.helpers import run_cli_command


def test_context_creates_default_perm_context_file(tmp_path: Path, monkeypatch):
    """
    Scenario 2: Simplified Default Configuration
    Given a project that does not have a .teddy/global.context file
    When the user runs the `teddy context` command for the first time
    Then a new file .teddy/global.context MUST be created.
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

    # Check global.context
    perm_context_file = teddy_dir / "global.context"
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
    (tmp_path / ".teddy/global.context").write_text(
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

    # Assert - Standardized Output Format (Scenario 1)
    assert result.exit_code == 0
    assert "# System Information" in output
    assert "# Repository Tree" in output
    assert "# Context Vault" in output
    assert "# File Contents" in output

    # Find the order of headers
    positions = {
        header: output.find(header)
        for header in [
            "# System Information",
            "# Repository Tree",
            "# Context Vault",
            "# File Contents",
        ]
    }
    assert -1 not in positions.values(), "One or more headers are missing"
    assert (
        positions["# System Information"]
        < positions["# Repository Tree"]
        < positions["# Context Vault"]
        < positions["# File Contents"]
    ), "Headers are not in the correct order"

    # Assert on System Information content
    sys_info_match = re.search(
        r"# System Information(.*?)# Repository Tree", output, re.DOTALL
    )
    assert sys_info_match is not None, "System Information section not found"
    sys_info_section = sys_info_match.group(1)
    assert "shell:" in sys_info_section
    assert "python_version:" not in sys_info_section

    # Assert - Clean Context Vault Listing (Scenario 3)
    context_vault_match = re.search(
        r"# Context Vault(.*?)# File Contents", output, re.DOTALL
    )
    assert context_vault_match is not None, "Context Vault section not found"
    context_vault_section = context_vault_match.group(1).strip()
    # The vault should list all requested files, even non-existent ones
    assert "README.md" in context_vault_section
    assert "docs/ARCHITECTURE.md" in context_vault_section
    assert "non_existent_file.md" in context_vault_section
    assert "```" not in context_vault_section

    # Assert - File Contents (Scenario 1 & missing file reporting)
    file_contents_match = re.search(r"# File Contents(.*)", output, re.DOTALL)
    assert file_contents_match is not None, "File Contents section not found"
    file_contents_section = file_contents_match.group(1)

    assert "## [README.md](/README.md)" in file_contents_section
    assert "## [docs/ARCHITECTURE.md](/docs/ARCHITECTURE.md)" in file_contents_section
    assert "## non_existent_file.md (Not Found)" in file_contents_section

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
    (tmp_path / ".teddy/global.context").write_text(
        "main.py\nconfig.cfg\n", encoding="utf-8"
    )
    (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "config.cfg").write_text("debug=true", encoding="utf-8")

    # Act
    result = run_cli_command(monkeypatch, ["context"], cwd=tmp_path)
    output = result.stdout

    # Assert
    assert result.exit_code == 0
    assert "```python\nprint('hello')\n```" in output
    assert "```ini\ndebug=true\n```" in output
