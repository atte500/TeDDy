import pathlib
from unittest.mock import patch

import pytest
import yaml

from tests.acceptance.helpers import run_teddy_command

# Mark all tests in this module as using the 'tmp_path' fixture
pytestmark = pytest.mark.usefixtures("tmp_path")


def test_execute_plan_interactively(tmp_path: pathlib.Path):
    """
    Scenario: Execute a plan with interactive approval.
    - Given a valid plan file exists.
    - When I run `teddy execute <plan_file>` in my terminal.
    - Then the application should prompt me for approval (`y/n`).
    - And if I approve, the action is executed.
    """
    # Arrange
    plan = [
        {
            "action": "create_file",
            "path": "test_file.txt",
            "content": "Hello, World!",
        }
    ]
    plan_file = tmp_path / "plan.yaml"
    plan_file.write_text(yaml.dump(plan))
    new_file_path = tmp_path / "test_file.txt"

    # Act & Assert
    # We mock the user prompt to approve the action.
    # We pass the plan via a file, avoiding clipboard/subprocess mocking issues.
    with patch("rich.prompt.Confirm.ask", return_value=True):
        result = run_teddy_command(["execute", str(plan_file)], cwd=tmp_path)

    # Assert execution report
    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    assert report["action_logs"][0]["status"] == "COMPLETED"

    # Assert file system side-effect
    assert new_file_path.exists()
    assert new_file_path.read_text() == "Hello, World!"
