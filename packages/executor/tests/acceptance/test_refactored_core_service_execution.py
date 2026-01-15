from pathlib import Path
from unittest.mock import patch
import yaml
from typer.testing import CliRunner

from teddy_executor.main import app, create_container


def test_successful_plan_execution_with_refactored_services(tmp_path: Path):
    """
    Given a valid plan,
    When the user runs the executor,
    Then the new service layer should execute the plan successfully.
    """
    # Arrange
    runner = CliRunner(mix_stderr=False)
    target_file = tmp_path / "hello.txt"
    plan_structure = [
        {
            "action": "create_file",
            "params": {"path": str(target_file), "content": "Hello, World!"},
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
    assert target_file.exists()
    assert target_file.read_text() == "Hello, World!"

    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    assert report["action_logs"][0]["status"] == "SUCCESS"
