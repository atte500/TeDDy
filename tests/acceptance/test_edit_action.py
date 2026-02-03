from pathlib import Path
from unittest.mock import patch
import yaml
from typer.testing import CliRunner

from teddy_executor.main import app, create_container
from .helpers import parse_yaml_report


def test_edit_action_happy_path(tmp_path: Path):
    """
    Given a plan to edit an existing file,
    When the plan is executed,
    Then the file content should be updated correctly.
    """
    # Arrange
    runner = CliRunner()
    file_to_edit = tmp_path / "test_file.txt"
    original_content = "Hello world, this is a test."
    file_to_edit.write_text(original_content)

    plan_structure = [
        {
            "action": "edit",
            "params": {
                "path": str(file_to_edit),
                "find": "world",
                "replace": "planet",
            },
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
    assert result.exit_code == 0
    assert file_to_edit.read_text() == "Hello planet, this is a test."

    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    assert report["action_logs"][0]["status"] == "SUCCESS"


def test_edit_action_file_not_found(tmp_path: Path):
    """
    Given a plan to edit a non-existent file,
    When the plan is executed,
    Then the action should fail and report the error.
    """
    # Arrange
    runner = CliRunner()
    non_existent_file = tmp_path / "non_existent.txt"
    plan_structure = [
        {
            "action": "edit",
            "params": {
                "path": str(non_existent_file),
                "find": "foo",
                "replace": "bar",
            },
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
    assert result.exit_code == 1
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "FAILURE"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"
    assert "No such file or directory" in action_log["details"]
