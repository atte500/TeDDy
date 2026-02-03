from pathlib import Path
from unittest.mock import patch
import yaml
from typer.testing import CliRunner

from teddy_executor.main import app, create_container


def test_edit_action_fails_on_multiple_occurrences(tmp_path: Path):
    """
    Given a file with multiple occurrences of the find string,
    When an edit action is executed,
    Then the action should fail to prevent ambiguity.
    """
    # Arrange
    runner = CliRunner()
    file_to_edit = tmp_path / "test.txt"
    original_content = "hello world, hello again"
    file_to_edit.write_text(original_content)

    plan_structure = [
        {
            "action": "edit",
            "params": {
                "path": str(file_to_edit),
                "find": "hello",
                "replace": "goodbye",
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
    assert file_to_edit.read_text() == original_content  # File should be unchanged

    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "FAILURE"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"
    assert "Aborting edit to prevent ambiguity" in action_log["details"]
