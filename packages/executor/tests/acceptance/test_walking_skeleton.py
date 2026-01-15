from pathlib import Path
from unittest.mock import patch
import yaml
from typer.testing import CliRunner

from teddy_executor.main import app, create_container


def test_successful_execution(tmp_path: Path):
    """
    Given a valid YAML plan with a single 'echo' command,
    When the plan is run via the CLI,
    Then the command should exit with status 0,
    And the report should show SUCCESS with the correct output.
    """
    # ARRANGE
    runner = CliRunner(mix_stderr=False)
    plan_structure = [
        {"action": "execute", "params": {"command": 'echo "hello world"'}}
    ]
    plan_content = yaml.dump(plan_structure)
    plan_file = tmp_path / "plan.yml"
    plan_file.write_text(plan_content)

    real_container = create_container()

    # ACT
    with patch("teddy_executor.main.container", real_container):
        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

    # ASSERT
    assert result.exit_code == 0, (
        f"Teddy should exit with 0 on success. Output: {result.stdout}"
    )

    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"

    # The 'details' field is already a dict because of yaml.safe_load
    details_dict = action_log["details"]
    assert "hello world" in details_dict.get("stdout", "")


def test_failed_execution(tmp_path: Path):
    """
    Given a valid YAML plan with a failing command,
    When the plan is run via the CLI,
    Then the command should exit with a non-zero code,
    And the report should show FAILURE with the correct error output.
    """
    # ARRANGE
    runner = CliRunner(mix_stderr=False)
    plan_structure = [
        {"action": "execute", "params": {"command": "nonexistentcommand12345"}}
    ]
    plan_content = yaml.dump(plan_structure)
    plan_file = tmp_path / "plan.yml"
    plan_file.write_text(plan_content)

    real_container = create_container()

    # ACT
    with patch("teddy_executor.main.container", real_container):
        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

    # ASSERT
    assert result.exit_code == 1, "Teddy should exit with 1 on failure"

    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "FAILURE"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"

    # The 'details' field is a dict; the error message is in 'stderr'
    details_dict = action_log["details"]
    error_msg = details_dict.get("stderr", "").lower()
    assert "not found" in error_msg or "no such file" in error_msg
