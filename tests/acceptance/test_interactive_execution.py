from pathlib import Path
from unittest.mock import MagicMock, patch
import yaml
from typer.testing import CliRunner

from teddy_executor.main import app, create_container
from teddy_executor.core.ports.outbound import IUserInteractor
from .helpers import parse_yaml_report


def test_interactive_approval_and_execution(tmp_path: Path):
    """
    Given a plan from the clipboard,
    When the user runs `execute` interactively and approves,
    Then the action should be executed successfully.
    """
    # Arrange
    runner = CliRunner()
    test_file = tmp_path / "test_file.txt"
    plan_structure = [
        {
            "action": "create_file",
            "params": {"path": str(test_file), "content": "Interactive Hello"},
        }
    ]
    plan_yaml = yaml.dump(plan_structure)

    # Mock the UserInteractor to simulate user approval
    mock_interactor = MagicMock(spec=IUserInteractor)
    mock_interactor.confirm_action.return_value = (True, "")

    test_container = create_container()
    test_container.register(IUserInteractor, instance=mock_interactor)

    # Act
    with patch("teddy_executor.main.pyperclip.paste", return_value=plan_yaml):
        with patch("teddy_executor.main.container", test_container):
            result = runner.invoke(app, ["execute"])  # No --yes flag for interactive

    # Assert
    assert result.exit_code == 0
    assert test_file.exists()
    assert test_file.read_text() == "Interactive Hello"
    mock_interactor.confirm_action.assert_called_once()

    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"


def test_interactive_skip_with_reason(tmp_path: Path):
    """
    Given a plan from the clipboard,
    When the user runs `execute` interactively and denies with a reason,
    Then the action should be skipped and the reason reported.
    """
    # Arrange
    runner = CliRunner()
    test_file = tmp_path / "test.txt"
    plan_structure = [{"action": "create_file", "params": {"path": str(test_file)}}]
    plan_yaml = yaml.dump(plan_structure)

    # Mock the UserInteractor to simulate user denial with a reason
    mock_interactor = MagicMock(spec=IUserInteractor)
    mock_interactor.confirm_action.return_value = (False, "Manual check needed")

    test_container = create_container()
    test_container.register(IUserInteractor, instance=mock_interactor)

    # Act
    with patch("teddy_executor.main.pyperclip.paste", return_value=plan_yaml):
        with patch("teddy_executor.main.container", test_container):
            # We must provide some input to stdin to satisfy the `input()`
            # call inside the mocked `confirm_action` if it were real.
            # Even with a mock, Typer's runner may expect it.
            result = runner.invoke(app, ["execute"], input="n\nManual check needed\n")

    # Assert
    assert result.exit_code == 1  # A skipped plan is a failed plan
    assert not test_file.exists()

    report = parse_yaml_report(result.stdout)
    # The run is a FAILURE because an action did not complete successfully
    assert report["run_summary"]["status"] == "FAILURE"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SKIPPED"
    expected_details = "User skipped this action. Reason: Manual check needed"
    assert action_log["details"] == expected_details
