import subprocess
import sys
from pathlib import Path
import textwrap


def run_teddy(plan: str, cwd: Path) -> subprocess.CompletedProcess:
    """Helper function to run the teddy CLI."""
    return subprocess.run(
        [sys.executable, "-m", "teddy"],
        input=plan,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_successfully_editing_multiline_content(tmp_path: Path):
    """
    Tests that the 'edit' action works with multiline find and replace blocks.
    """
    # Arrange
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    file_to_edit = test_dir / "file.txt"
    initial_content = textwrap.dedent(
        """
        dependencies:
          - name: typer
            version: 0.4.0
          - name: pytest
            version: 8.0.0
    """
    )
    file_to_edit.write_text(initial_content)

    find_block = textwrap.dedent(
        """
        - name: typer
          version: 0.4.0
    """
    ).strip()

    replace_block = textwrap.dedent(
        """
        - name: typer
          version: 0.5.0
    """
    ).strip()

    # Correctly indent the blocks for valid YAML content.
    # The `find:` key is at 8 spaces in the dedented plan. Content needs more (e.g., 10).
    indented_find = textwrap.indent(find_block, "          ")
    indented_replace = textwrap.indent(replace_block, "          ")

    plan = textwrap.dedent(
        f"""
    - action: edit
      params:
        file_path: "file.txt"
        find: |
{indented_find}
        replace: |
{indented_replace}
    """
    )

    # Act
    result = run_teddy(plan, cwd=test_dir)

    # Assert
    expected_content = textwrap.dedent(
        """
        dependencies:
          - name: typer
            version: 0.5.0
          - name: pytest
            version: 8.0.0
    """
    )
    updated_content = file_to_edit.read_text()

    assert updated_content == expected_content
    assert result.returncode == 0
    assert "Run Summary: SUCCESS" in result.stdout


def test_successfully_editing_a_file(tmp_path: Path):
    """
    Given a file exists with some content,
    When a plan is executed with an 'edit' action to replace a string,
    Then the file content should be updated.
    """
    # Arrange
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    file_to_edit = test_dir / "file.txt"
    initial_content = "Hello world!"
    file_to_edit.write_text(initial_content)

    plan = textwrap.dedent(
        """
        - action: edit
          params:
            file_path: "file.txt"
            find: "world"
            replace: "TeDDy"
    """
    )

    # Act
    result = run_teddy(plan, cwd=test_dir)

    # Assert
    # Primary assertion: The side effect on the file system must be correct.
    updated_content = file_to_edit.read_text()
    assert updated_content == "Hello TeDDy!"

    # Secondary assertions: The process should report success.
    assert result.returncode == 0
    assert "Run Summary: SUCCESS" in result.stdout
    assert "Status:** COMPLETED" in result.stdout


def test_editing_non_existent_file_fails_gracefully(tmp_path: Path):
    """
    Given no file exists at a certain path,
    When a plan is executed with an 'edit' action targeting that path,
    Then the execution should fail with a clear error message.
    """
    # Arrange
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()

    plan = textwrap.dedent(
        """
        - action: edit
          params:
            file_path: "non_existent_file.txt"
            find: "any"
            replace: "thing"
    """
    )

    # Act
    result = run_teddy(plan, cwd=test_dir)

    # Assert
    # Primary assertion: The process should exit with a failure code.
    assert result.returncode != 0

    # Secondary assertions: The process should report failure and a clear error message.
    assert "Run Summary: FAILURE" in result.stdout
    assert "Status:** FAILURE" in result.stdout
    assert "No such file or directory" in result.stdout


def test_editing_file_where_find_text_is_not_found_fails(tmp_path: Path):
    """
    Given a file with content,
    When a plan is executed to replace text that doesn't exist,
    Then the execution should fail with a clear error message.
    """
    # Arrange
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    file_to_edit = test_dir / "file.txt"
    initial_content = "Hello world!"
    file_to_edit.write_text(initial_content)

    plan = textwrap.dedent(
        """
        - action: edit
          params:
            file_path: "file.txt"
            find: "goodbye"
            replace: "farewell"
    """
    )

    # Act
    result = run_teddy(plan, cwd=test_dir)

    # Assert
    # The file content should be unchanged.
    assert file_to_edit.read_text() == initial_content

    # The process should exit with a failure code.
    assert result.returncode != 0

    # The report should indicate failure and the specific reason.
    assert "Run Summary: FAILURE" in result.stdout
    assert "Status:** FAILURE" in result.stdout
    assert "Search text was not found" in result.stdout
    assert (
        initial_content in result.stdout
    )  # The original content should be in the output.
