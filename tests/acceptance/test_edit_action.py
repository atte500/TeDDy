from pathlib import Path

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
    # The new validation logic catches this before execution
    # So the status is FAILURE (mapped from VALIDATION_FAILED)
    assert report["run_summary"]["status"] == "FAILURE"
    # Validation errors are not in action_logs, so we skip checking action_logs
    # and instead verify the error message in the output if possible, or just accept the status.
    assert "File to edit does not exist" in result.stdout
