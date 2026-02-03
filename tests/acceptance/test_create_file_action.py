from pathlib import Path
from unittest.mock import patch
import yaml
from typer.testing import CliRunner

from teddy_executor.main import app, create_container
from .helpers import parse_yaml_report


def test_create_file_happy_path(tmp_path: Path):
    """
    Given a YAML plan to create a new file,
    When the user executes the plan,
    Then the file should be created with the correct content and the report is valid.
    """
    # Arrange
    runner = CliRunner()
    file_name = "new_file.txt"
    new_file_path = tmp_path / file_name
    plan_structure = [
        {
            "action": "create_file",
            "params": {"path": str(new_file_path), "content": "Hello, World!"},
        }
    ]
    plan_content = yaml.dump(plan_structure)
    plan_file = tmp_path / "plan.yml"
    plan_file.write_text(plan_content)

    real_container = create_container()

    # Act
    with patch("teddy_executor.main.container", real_container):
        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

    # Assert
    assert result.exit_code == 0, f"Teddy failed with stderr: {result.stderr}"
    assert new_file_path.exists(), "The new file was not created."
    assert new_file_path.read_text() == "Hello, World!", (
        "The file content is incorrect."
    )

    # Verify the report output
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"


def test_create_file_when_file_exists_fails_gracefully(tmp_path: Path):
    """
    Given a file that already exists,
    When a plan is executed to create the same file,
    Then the action should fail, the original file should be unchanged,
    and the report should indicate the failure.
    """
    # Arrange
    runner = CliRunner()
    existing_file = tmp_path / "existing.txt"
    original_content = "Original content"
    existing_file.write_text(original_content)

    plan_structure = [
        {
            "action": "create_file",
            "params": {"path": str(existing_file), "content": "Hello, World!"},
        }
    ]
    plan_content = yaml.dump(plan_structure)
    plan_file = tmp_path / "plan.yml"
    plan_file.write_text(plan_content)

    real_container = create_container()

    # Act
    with patch("teddy_executor.main.container", real_container):
        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

    # Assert
    assert result.exit_code == 1, (
        "Teddy should exit with a non-zero code on plan failure"
    )
    assert existing_file.read_text() == original_content

    # The report should clearly indicate the failure
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "FAILURE"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"
    assert "File exists" in action_log["details"]
