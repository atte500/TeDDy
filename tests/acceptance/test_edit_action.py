from pathlib import Path
from textwrap import dedent, indent

from .helpers import parse_yaml_report, run_cli_with_plan


def test_edit_action_happy_path(monkeypatch, tmp_path: Path):
    """
    Given a plan to edit an existing file,
    When the plan is executed,
    Then the file content should be updated correctly.
    """
    # Arrange
    file_to_edit = tmp_path / "test_file.txt"
    file_to_edit.write_text("Hello world, this is a test.")

    plan = [
        {
            "action": "edit",
            "description": "Test basic find and replace.",
            "params": {
                "path": file_to_edit,
                "find": "world",
                "replace": "planet",
            },
        }
    ]

    # Act
    result = run_cli_with_plan(monkeypatch, plan, tmp_path)

    # Assert
    assert result.exit_code == 0
    assert file_to_edit.read_text() == "Hello planet, this is a test."

    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    assert report["action_logs"][0]["status"] == "SUCCESS"


def test_edit_action_file_not_found(monkeypatch, tmp_path: Path):
    """
    Given a plan to edit a non-existent file,
    When the plan is executed,
    Then the action should fail and report the error.
    """
    # Arrange
    non_existent_file = tmp_path / "non_existent.txt"
    plan = [
        {
            "action": "edit",
            "description": "Test edit on non-existent file.",
            "params": {"path": non_existent_file, "find": "foo", "replace": "bar"},
        }
    ]

    # Act
    result = run_cli_with_plan(monkeypatch, plan, tmp_path)

    # Assert
    assert result.exit_code == 1
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "FAILURE"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"
    assert "No such file or directory" in action_log["details"]


def test_edit_action_handles_multiline_with_indentation(monkeypatch, tmp_path: Path):
    """
    Given a plan to perform a multiline edit with indentation,
    When the plan is executed,
    Then the file should be updated correctly because the replace block is
    a literal with the correct indentation provided.
    """
    # Arrange
    file_to_edit = tmp_path / "my_class.py"
    original_content = dedent(
        """\
        class MyClass:
            def __init__(self, value):
                self.value = value

            def existing_method(self):
                \"\"\"An existing method.\"\"\"
                return self.value
        """
    )
    file_to_edit.write_text(original_content)

    # The find block is unindented via dedent, but the match logic will find
    # the indented version in the source file.
    find_block = dedent(
        """\
        def existing_method(self):
            \"\"\"An existing method.\"\"\"
            return self.value
        """
    )

    # The replace block must be a literal with the correct final indentation.
    # We construct it by indenting the unindented source text.
    unindented_replace_block = dedent(
        """\
        def existing_method(self):
            \"\"\"An existing method.\"\"\"
            return self.value

        def new_indented_method(self, multiplier):
            \"\"\"A new method added via edit.\"\"\"
            return self.value * multiplier
        """
    )
    replace_block = indent(unindented_replace_block, "    ")

    expected_content = (
        dedent(
            """\
        class MyClass:
            def __init__(self, value):
                self.value = value

        """
        )
        + replace_block
    )
    # Remove the final newline added by dedent for accurate comparison
    expected_content = expected_content.strip()

    plan = [
        {
            "action": "edit",
            "description": "Test multiline edit with literal indentation.",
            "params": {
                "path": file_to_edit,
                "find": find_block,
                "replace": replace_block,
            },
        }
    ]

    # Act
    result = run_cli_with_plan(monkeypatch, plan, tmp_path)

    # Assert
    assert result.exit_code == 0, f"CLI command failed: {result.stdout}"

    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS", f"Run failed: {report}"
    assert report["action_logs"][0]["status"] == "SUCCESS", f"Action failed: {report}"

    actual_content = file_to_edit.read_text().strip()
    assert actual_content == expected_content
