from pathlib import Path
from tests.acceptance.helpers import run_teddy_command


def test_context_command_first_run(tmp_path: Path):
    """
    Scenario: First-time run in a new project
    Given I am in a project directory that does not contain a .teddy folder
    When I run the `teddy context` command
    Then a .teddy directory is created
    And a .teddy/.gitignore file is created containing the line `*`
    And a .teddy/context.txt file is created
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

    context_txt = teddy_dir / "context.txt"
    assert context_txt.is_file(), ".teddy/context.txt was not created."

    permanent_context = teddy_dir / "permanent_context.txt"
    assert permanent_context.is_file(), ".teddy/permanent_context.txt was not created."

    # Check for default content in permanent_context.txt
    permanent_content = permanent_context.read_text()
    assert "README.md" in permanent_content
    assert "docs/ARCHITECTURE.md" in permanent_content
    assert "repotree.txt" in permanent_content


def test_context_command_honors_teddyignore_overrides(tmp_path: Path):
    """
    Scenario: Re-include a file ignored by .gitignore
    Given a project with a file "dist/index.html" and "dist/bundle.js"
    And a ".gitignore" file containing "dist/"
    And a ".teddyignore" file containing "!dist/index.html"
    When the user runs the "teddy context" command
    Then the generated repotree output should contain "dist/index.html"
    And the generated repotree output should not contain "dist/bundle.js"
    """
    # Arrange
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text("<html></html>")
    (dist_dir / "bundle.js").write_text("console.log('hello');")

    (tmp_path / ".gitignore").write_text("dist/\n")
    (tmp_path / ".teddyignore").write_text("!dist/index.html\n")

    # To trigger repotree generation, we need to tell the context command
    # to look for it. We'll create the .teddy dir and context.txt manually.
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    (teddy_dir / "context.txt").write_text(".teddy/repotree.txt")

    # Act
    result = run_teddy_command(args=["context"], cwd=tmp_path)

    # Assert
    assert result.returncode == 0, f"Teddy exited with an error:\n{result.stderr}"

    # The final output to stdout should contain the repotree.
    # Assert that the output has the new indented list structure.
    output = result.stdout

    # The output of the `context` command includes headers and other info.
    # We need to extract just the content of the repotree.txt file.
    # A simple way is to find the file header and check the lines that follow.
    repotree_content_header = "--- File: .teddy/repotree.txt ---"
    assert repotree_content_header in output

    # Extract the content after the header
    repotree_content = output.split(repotree_content_header)[1]

    # The generated tree should be in the content
    # Note: The root directory name is dynamic, so we just check for the structure inside it
    assert "dist/" in repotree_content
    assert "  index.html" in repotree_content
    assert "bundle.js" not in repotree_content
