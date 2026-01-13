from pathlib import Path
from .helpers import run_teddy_with_plan_structure, parse_yaml_report


def test_create_file_happy_path(tmp_path: Path):
    """
    Given a YAML plan to create a new file,
    When the user executes the plan,
    Then the file should be created with the correct content and the report is valid.
    """
    # Arrange
    file_name = "new_file.txt"
    new_file_path = tmp_path / file_name
    plan_structure = [
        {
            "action": "create_file",
            "params": {"file_path": new_file_path, "content": "Hello, World!"},
        }
    ]

    # Act
    result = run_teddy_with_plan_structure(plan_structure, cwd=tmp_path)

    # Assert
    assert result.returncode == 0, f"Teddy failed with stderr: {result.stderr}"
    assert new_file_path.exists(), "The new file was not created."
    assert new_file_path.read_text() == "Hello, World!", (
        "The file content is incorrect."
    )

    # Verify the report output
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "COMPLETED"
    assert action_log["action"]["type"] == "create_file"
    assert action_log["action"]["params"]["file_path"] == new_file_path.as_posix()


def test_create_file_when_file_exists_fails_gracefully(tmp_path: Path):
    """
    Given a file that already exists,
    When a plan is executed to create the same file,
    Then the action should fail, the original file should be unchanged,
    and the report should indicate the failure.
    """
    # Arrange
    existing_file = tmp_path / "existing.txt"
    original_content = "Original content"
    existing_file.write_text(original_content)

    plan_structure = [
        {
            "action": "create_file",
            "params": {"file_path": existing_file, "content": "Hello, World!"},
        }
    ]

    # Act
    result = run_teddy_with_plan_structure(plan_structure, cwd=tmp_path)

    # Assert
    # The tool should exit with a failure code because the plan failed
    assert result.returncode != 0, (
        "Teddy should exit with a non-zero code on plan failure"
    )

    # The original file should not have been modified
    assert existing_file.read_text() == original_content

    # The report should clearly indicate the failure
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "FAILURE"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"
    assert "File exists" in action_log["error"]
