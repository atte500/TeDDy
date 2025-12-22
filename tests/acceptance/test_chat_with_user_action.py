from pathlib import Path
import pytest
import yaml

from .helpers import run_teddy_as_subprocess, validate_teddy_output

# A plan containing a CHAT_WITH_USER action
PLAN_WITH_CHAT_ACTION = {
    "plan": [
        {
            "action": "CHAT_WITH_USER",
            "title": "Ask for user's favorite color",
            "prompt": "What is your favorite color?",
        }
    ]
}


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
    # The user will first be asked to approve the action, then provide the input.
    # The input is "Blue" followed by two newlines to terminate.
    user_input = "y\nBlue\n\n"

    # Act
    process = run_teddy_as_subprocess(plan_file, input=user_input)
    output = process.stdout

    # Assert
    # The teddy output should be a valid list of dictionaries
    teddy_output = validate_teddy_output(output)

    # There should be one action report
    assert len(teddy_output) == 1
    action_report = teddy_output[0]

    # The action should be marked as SUCCEEDED
    assert action_report["status"] == "SUCCEEDED"

    # The report details should contain the user's response
    assert "response" in action_report["details"]
    assert action_report["details"]["response"] == "Blue"
