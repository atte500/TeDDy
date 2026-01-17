from pathlib import Path
from unittest.mock import MagicMock, patch
import yaml
from typer.testing import CliRunner

from teddy_executor.main import app, create_container
from teddy_executor.core.ports.outbound import IUserInteractor

runner = CliRunner(mix_stderr=False)


def test_interactive_prompt_shows_description(tmp_path: Path):
    """
    Given a plan with an action that has a 'description' field,
    When the user runs `execute` interactively,
    Then the confirmation prompt should include the description.
    """
    # Arrange
    test_file = tmp_path / "test.txt"
    plan_structure = {
        "actions": [
            {
                "action": "create_file",
                "description": "Create a test file for the QoL feature.",
                "path": str(test_file),
                "content": "hello",
            }
        ]
    }
    plan_yaml = yaml.dump(plan_structure)
    plan_file = tmp_path / "plan.yaml"
    plan_file.write_text(plan_yaml)

    # Mock the UserInteractor to simulate user approval and capture the prompt
    mock_interactor = MagicMock(spec=IUserInteractor)
    mock_interactor.confirm_action.return_value = (True, "")

    test_container = create_container()
    test_container.register(IUserInteractor, instance=mock_interactor)

    # Act
    with patch("teddy_executor.main.container", test_container):
        result = runner.invoke(app, ["execute", str(plan_file)])

    # Assert
    assert result.exit_code == 0
    assert test_file.exists()

    # Verify the prompt sent to the user included the description
    mock_interactor.confirm_action.assert_called_once()
    call_args, _ = mock_interactor.confirm_action.call_args
    prompt_message = call_args[0]
    assert "Create a test file for the QoL feature." in prompt_message
