import textwrap
from pathlib import Path
import yaml
from .helpers import run_teddy_with_plan_structure


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

    plan_structure = [
        {
            "action": "edit",
            "params": {
                "file_path": "file.txt",
                "find": "Let's edit this line.",
                "replace": "This line has been successfully edited.",
            },
        }
    ]

    # Act
    result = run_teddy_with_plan_structure(plan_structure, cwd=test_dir)

    # Assert
    expected_content = textwrap.dedent(
        """\
        Hello world!
        This is a test file.
        This line has been successfully edited.
        This is the final line.
        """
    )
    assert file_to_edit.read_text() == expected_content

    assert result.returncode == 0
    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "COMPLETED"


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
    plan_structure = [
        {
            "action": "edit",
            "params": {"file_path": "file.txt", "find": "", "replace": new_content},
        }
    ]

    # Act
    result = run_teddy_with_plan_structure(plan_structure, cwd=test_dir)

    # Assert
    assert file_to_edit.read_text() == new_content
    assert result.returncode == 0
    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "COMPLETED"


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

    plan_structure = [
        {
            "action": "edit",
            "params": {
                "file_path": "source.py",
                "find": find_block,
                "replace": replace_block,
            },
        }
    ]

    # Act
    result = run_teddy_with_plan_structure(plan_structure, cwd=test_dir)

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
    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    assert report["action_logs"][0]["status"] == "COMPLETED"


def test_editing_non_existent_file_fails_gracefully(tmp_path: Path):
    """
    Given no file exists at a certain path,
    When a plan is executed with an 'edit' action targeting that path,
    Then the execution should fail with a clear error message.
    """
    # Arrange
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()

    plan_structure = [
        {
            "action": "edit",
            "params": {
                "file_path": "non_existent_file.txt",
                "find": "any",
                "replace": "thing",
            },
        }
    ]

    # Act
    result = run_teddy_with_plan_structure(plan_structure, cwd=test_dir)

    # Assert
    assert result.returncode != 0
    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "FAILURE"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"
    assert "No such file or directory" in action_log["error"]
    assert action_log["output"] is None


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

    plan_structure = [
        {
            "action": "edit",
            "params": {
                "file_path": "file.txt",
                "find": "goodbye",
                "replace": "farewell",
            },
        }
    ]

    # Act
    result = run_teddy_with_plan_structure(plan_structure, cwd=test_dir)

    # Assert
    assert file_to_edit.read_text() == initial_content
    assert result.returncode != 0
    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "FAILURE"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"
    assert "Search text 'goodbye' not found" in action_log["error"]
    assert action_log["output"] == initial_content
