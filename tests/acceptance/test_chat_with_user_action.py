from pathlib import Path
import pytest
import yaml

from .helpers import run_teddy_as_subprocess

# A plan containing a chat_with_user action.
# Note the top-level list, lowercase action name, and 'params' key.
PLAN_WITH_CHAT_ACTION = [
    {
        "action": "chat_with_user",
        "title": "Ask for user's favorite color",
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
    # The user input is "Blue" followed by an empty line to terminate input.
    # There is no "y/n" approval for this action type.
    user_input = "Blue\n\n"

    # Act
    process = run_teddy_as_subprocess(plan_file, input=user_input)
    output = process.stdout

    # Assert
    # The overall run should be successful
    assert "Run Summary: SUCCESS" in output

    # The action report should show SUCCESS
    # Note: PlanService returns SUCCESS for this action, not COMPLETED.
    assert "- **Status:** SUCCESS" in output

    # The report should contain the user's response in the output section
    assert "- **Output:**" in output
    assert "Blue" in output
