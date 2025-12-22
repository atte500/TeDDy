import textwrap
from pathlib import Path

from .helpers import run_teddy_with_stdin


def test_editing_a_file_happy_path(tmp_path: Path):
    """
    Given a file with some initial content,
    When a plan is executed with a valid 'edit' action,
    Then the file should be modified with the new content.
    """
    # Arrange
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    file_to_edit = test_dir / "file.txt"
    initial_content = textwrap.dedent(
        """\
        Hello world!
        This is a test file.
        Let's edit this line.
        This is the final line.
        """
    )
    file_to_edit.write_text(initial_content)

    plan = textwrap.dedent(
        """
        - action: edit
          params:
            file_path: "file.txt"
            find: "Let's edit this line."
            replace: "This line has been successfully edited."
    """
    )

    # Act
    result = run_teddy_with_stdin(plan, cwd=test_dir)

    # Assert
    # Primary assertion: The file content should be updated.
    expected_content = textwrap.dedent(
        """\
        Hello world!
        This is a test file.
        This line has been successfully edited.
        This is the final line.
        """
    )
    assert file_to_edit.read_text() == expected_content

    # Secondary assertions: The process should exit successfully and report completion.
    assert result.returncode == 0
    assert "Run Summary: SUCCESS" in result.stdout
    assert "- **Status:** COMPLETED" in result.stdout


def test_editing_with_empty_find_replaces_entire_file(tmp_path: Path):
    """
    Given a file with initial content,
    When a plan is executed with an 'edit' action where 'find' is an empty string,
    Then the entire content of the file should be replaced.
    """
    # Arrange
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    file_to_edit = test_dir / "file.txt"
    file_to_edit.write_text("This is the original content.")

    new_content = "This is the new, full content."
    plan = textwrap.dedent(
        f"""
        - action: edit
          params:
            file_path: "file.txt"
            find: ""
            replace: "{new_content}"
    """
    )

    # Act
    result = run_teddy_with_stdin(plan, cwd=test_dir)

    # Assert
    # Primary assertion: The file content should be completely replaced.
    assert file_to_edit.read_text() == new_content

    # Secondary assertions: The process should report success.
    assert result.returncode == 0
    assert "- **Status:** COMPLETED" in result.stdout


def test_multiline_edit_preserves_indentation(tmp_path: Path):
    """
    Given a file with indented code,
    When a plan is executed to replace a multiline block,
    Then the new content should adopt the indentation of the original block.
    """
    # Arrange
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    file_to_edit = test_dir / "source.py"
    initial_content = textwrap.dedent(
        """\
        def my_function():
            print("Hello")
            # This is the block to be replaced
            if True:
                print("Old logic")
            # End of block
            print("Goodbye")
        """
    )
    file_to_edit.write_text(initial_content)

    find_block = textwrap.dedent(
        """\
        # This is the block to be replaced
        if True:
            print("Old logic")
        # End of block"""
    )

    replace_block = textwrap.dedent(
        """\
        # This is the new block
        if False:
            print("New logic")
        # End of new block"""
    )

    plan = f"""
    - action: edit
      params:
        file_path: "source.py"
        find: |
{textwrap.indent(find_block, '          ')}
        replace: |
{textwrap.indent(replace_block, '          ')}
    """

    # Act
    result = run_teddy_with_stdin(plan, cwd=test_dir)

    # Assert
    expected_content = textwrap.dedent(
        """\
        def my_function():
            print("Hello")
            # This is the new block
            if False:
                print("New logic")
            # End of new block
            print("Goodbye")
        """
    )
    assert file_to_edit.read_text() == expected_content
    assert result.returncode == 0


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
    result = run_teddy_with_stdin(plan, cwd=test_dir)

    # Assert
    # Primary assertion: The process should exit with a failure code.
    assert result.returncode != 0

    # Secondary assertions: The process should report failure and a clear error message.
    assert "Run Summary: FAILURE" in result.stdout
    assert "status: FAILURE" in result.stdout
    assert "No such file or directory" in result.stdout
    assert "output: |" not in result.stdout


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
    result = run_teddy_with_stdin(plan, cwd=test_dir)

    # Assert
    # The file content should be unchanged.
    assert file_to_edit.read_text() == initial_content

    # The process should exit with a failure code.
    assert result.returncode != 0

    # The report should indicate failure and the specific reason using the NEW format
    assert "Run Summary: FAILURE" in result.stdout
    assert "status: FAILURE" in result.stdout
    assert "error: Search text 'goodbye' not found in file." in result.stdout
    assert "output: |" in result.stdout
    assert f"    {initial_content}" in result.stdout
