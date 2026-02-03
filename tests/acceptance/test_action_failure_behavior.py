from pathlib import Path
from unittest.mock import patch

import yaml
from typer.testing import CliRunner

from .helpers import parse_yaml_report

from teddy_executor.main import app, create_container


def test_create_file_on_existing_file_fails_and_reports_correctly(tmp_path: Path):
    """
    Given a file that already exists,
    When a plan is executed to create the same file,
    Then the action should fail, the original file should be unchanged,
    and the report's details should contain the error message.
    """
    # ARRANGE
    runner = CliRunner()
    existing_file = tmp_path / "existing.txt"
    original_content = "original content"
    existing_file.write_text(original_content)

    plan_structure = {
        "actions": [
            {
                "type": "create_file",
                "params": {
                    "path": str(existing_file),
                    "content": "This is new content.",
                },
            }
        ]
    }
    plan_content = yaml.dump(plan_structure)
    plan_file = tmp_path / "plan.yml"
    plan_file.write_text(plan_content)

    # For an acceptance test, we use the real application container
    real_container = create_container()

    # ACT
    # The 'patch' is still necessary to ensure the CLI runner uses our container
    # instance, especially in a parallel test environment.
    with patch("teddy_executor.main.container", real_container):
        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

    # ASSERT
    assert result.exit_code == 1, (
        "Teddy should exit with a non-zero code on plan failure"
    )
    assert existing_file.read_text() == original_content, (
        "The original file should not be modified"
    )

    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "FAILURE"

    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"
    assert "File exists" in action_log["details"]
