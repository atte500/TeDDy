from pathlib import Path
from unittest.mock import patch
import yaml
from typer.testing import CliRunner

from teddy_executor.main import app, create_container
from .helpers import parse_yaml_report


def test_chat_with_user_action_successful(tmp_path: Path):
    """
    Given a plan containing a 'chat_with_user' action,
    When the plan is executed and the user provides input,
    Then the action should succeed and capture the response.
    """
    # Arrange
    runner = CliRunner()
    user_response = "Blue"
    # User input is the response, followed by an empty line to terminate.
    cli_input = f"{user_response}\n\n"

    plan_structure = [
        {
            "action": "chat_with_user",
            "params": {"prompt": "What is your favorite color?"},
        }
    ]
    plan_content = yaml.dump(plan_structure)
    plan_file = tmp_path / "plan.yml"
    plan_file.write_text(plan_content)

    real_container = create_container()

    # Act
    with patch("teddy_executor.main.container", real_container):
        result = runner.invoke(
            app, ["execute", str(plan_file), "--yes"], input=cli_input
        )

    # Assert
    assert result.exit_code == 0

    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"

    details_dict = action_log["details"]
    assert details_dict["response"] == user_response
