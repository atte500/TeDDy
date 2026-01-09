from pathlib import Path
from tests.acceptance.helpers import run_teddy_command


def test_context_command_first_run(tmp_path: Path):
    """
    Scenario: First-time run in a new project
    Given I am in a project directory that does not contain a .teddy folder
    When I run the `teddy context` command
    Then a .teddy directory is created with correctly commented default files.
    """
    from textwrap import dedent

    # Act
    result = run_teddy_command(args=["context"], cwd=tmp_path)

    # Assert
    assert result.returncode == 0, f"Teddy exited with an error:\n{result.stderr}"

    # Assert .teddy directory and .gitignore exist
    teddy_dir = tmp_path / ".teddy"
    assert teddy_dir.is_dir()
    assert (teddy_dir / ".gitignore").is_file()

    # Assert temp.context content
    temp_context = teddy_dir / "temp.context"
    assert temp_context.is_file()
    expected_temp_content = "# This file is managed by the AI. It determines the file context for the NEXT turn."
    assert temp_context.read_text().strip() == expected_temp_content

    # Assert perm.context content
    perm_context = teddy_dir / "perm.context"
    assert perm_context.is_file()
    expected_perm_content = dedent(
        """
        # This file is managed by the User. It provides persistent file context.
        .teddy/repotree.txt
        .teddy/temp.context
        .teddy/perm.context
        README.md
        docs/ARCHITECTURE.md
        """
    ).strip()
    assert perm_context.read_text().strip() == expected_perm_content

    # Assert repotree.txt content
    repotree = teddy_dir / "repotree.txt"
    assert repotree.is_file()
    # The tree is empty on first run, but should have the comment
    expected_repotree_content = "# This is the repotree of the project"
    assert repotree.read_text().strip() == expected_repotree_content


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
    # to look for it. We'll create the .teddy dir and temp.context manually.
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    (teddy_dir / "temp.context").write_text(".teddy/repotree.txt")

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
