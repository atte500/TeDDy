from pathlib import Path
import pytest
import yaml

from .helpers import run_teddy_with_plan_file

# A plan containing a chat_with_user action.
PLAN_WITH_CHAT_ACTION = [
    {
        "action": "chat_with_user",
        "params": {
            "prompt": "What is your favorite color?",
        },
    }
]


@pytest.fixture
def plan_file(tmp_path: Path) -> Path:
    """Creates a temporary plan file for the test."""
    p_file = tmp_path / "plan.yml"
    p_file.write_text(yaml.dump(PLAN_WITH_CHAT_ACTION))
    return p_file


def test_chat_with_user_action_successful(plan_file: Path):
    """
    Given a plan containing a 'chat_with_user' action,
    When the plan is executed,
    And the user provides input,
    Then the action should succeed and capture the response.
    """
    # Arrange
    # The user input is "Blue" followed by two newlines to terminate input.
    user_input = "Blue\n\n"

    # Act
    process = run_teddy_with_plan_file(plan_file, input=user_input, auto_approve=True)

    # Assert
    assert process.returncode == 0
    report = yaml.safe_load(process.stdout)

    # The overall run should be successful
    assert report["run_summary"]["status"] == "SUCCESS"

    # The action report should show SUCCESS and the user's response
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"
    assert action_log["output"] == "Blue"
    assert action_log["action"]["params"]["prompt"] == "What is your favorite color?"
