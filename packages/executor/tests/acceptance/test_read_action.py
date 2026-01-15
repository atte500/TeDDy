from pathlib import Path
from unittest.mock import patch
import yaml
from typer.testing import CliRunner

from teddy_executor.main import app, create_container


def test_read_action_happy_path(tmp_path: Path):
    """
    Given an existing file,
    When a 'read' action is executed,
    Then the action log's 'details' should contain the file's content.
    """
    # Arrange
    runner = CliRunner(mix_stderr=False)
    file_content = "Hello, this is the content."
    file_to_read = tmp_path / "readable.txt"
    file_to_read.write_text(file_content)

    plan_structure = [{"action": "read", "params": {"path": str(file_to_read)}}]
    plan_content = yaml.dump(plan_structure)
    plan_file = tmp_path / "plan.yml"
    plan_file.write_text(plan_content)

    real_container = create_container()

    # Act
    with patch("teddy_executor.main.container", real_container):
        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

    # Assert
    assert result.exit_code == 0
    report = yaml.safe_load(result.stdout)
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"

    # The 'details' field is already a dict because of yaml.safe_load
    details_dict = action_log["details"]
    assert details_dict["content"] == file_content


def test_read_action_file_not_found(tmp_path: Path):
    """
    Given a non-existent file path,
    When a 'read' action is executed,
    Then the action should fail and the report should indicate the error.
    """
    # Arrange
    runner = CliRunner(mix_stderr=False)
    non_existent_file = tmp_path / "non_existent.txt"
    plan_structure = [{"action": "read", "params": {"path": str(non_existent_file)}}]
    plan_content = yaml.dump(plan_structure)
    plan_file = tmp_path / "plan.yml"
    plan_file.write_text(plan_content)

    real_container = create_container()

    # Act
    with patch("teddy_executor.main.container", real_container):
        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

    # Assert
    assert result.exit_code == 1
    report = yaml.safe_load(result.stdout)
    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"
    assert "No such file or directory" in action_log["details"]
