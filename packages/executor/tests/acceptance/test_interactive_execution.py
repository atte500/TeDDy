from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from teddy_executor.main import app
from teddy_executor.core.services.plan_service import PlanService
from teddy_executor.core.services.action_factory import ActionFactory
from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)

# Using Typer's test runner is a "white-box" approach that allows mocks to work
# correctly because the test and the code run in the same process.
runner = CliRunner()


@pytest.fixture
def mock_pyperclip_paste():
    """Fixture to mock pyperclip.paste where it's looked up: in main.py"""
    with patch("teddy_executor.main.pyperclip.paste") as mock_paste:
        yield mock_paste


@pytest.fixture
def mock_pyperclip_copy():
    """Fixture to mock pyperclip.copy where it's looked up: in main.py"""
    with patch("teddy_executor.main.pyperclip.copy") as mock_copy:
        yield mock_copy


@pytest.fixture
def mock_console_interactor_class():
    """Fixture to mock the ConsoleInteractorAdapter class where it's looked up."""
    with patch("teddy_executor.main.ConsoleInteractorAdapter") as mock_adapter_class:
        # This setup simulates the user always approving.
        # Individual tests can override this behavior.
        mock_instance = MagicMock()
        mock_instance.confirm_action.return_value = (True, "")
        mock_adapter_class.return_value = mock_instance
        yield mock_instance


def test_execute_from_clipboard_with_interactive_approval(
    mock_pyperclip_paste: MagicMock,
    mock_pyperclip_copy: MagicMock,
    mock_console_interactor_class: MagicMock,
    tmp_path: Path,
):
    """
    Scenario 1: Execute Plan from Clipboard with Interactive Approval
    - Given I have a valid plan YAML in my system clipboard.
    - When I run `teddy execute` in my terminal.
    - Then the application should prompt me for approval (`y/n`) before executing each action.
    - And if I approve, the action is executed.
    """
    # Arrange
    test_file = tmp_path / "test_file.txt"
    plan_content = [
        {
            "action": "create_file",
            "params": {
                "file_path": str(test_file),
                "content": "Hello, World!",
            },
        },
    ]
    plan_yaml = yaml.dump(plan_content)
    mock_pyperclip_paste.return_value = plan_yaml

    # Act
    # Replicate the composition root to inject dependencies for the test run.
    # We use the mocked class for ConsoleInteractorAdapter.
    action_factory = ActionFactory()
    plan_service = PlanService(
        shell_executor=MagicMock(),
        file_system_manager=LocalFileSystemAdapter(),
        web_scraper=MagicMock(),
        action_factory=action_factory,
        user_interactor=mock_console_interactor_class,
        web_searcher=MagicMock(),
    )
    services = {"plan_service": plan_service, "context_service": MagicMock()}

    # We invoke the app directly, ensuring mocks are respected,
    # and pass the composed services via the `obj` parameter.
    result = runner.invoke(app, ["execute"], obj=services, catch_exceptions=False)

    # Assert
    assert result.exit_code == 0, f"STDOUT: {result.stdout}"

    # Verify side-effects
    assert test_file.exists()
    assert test_file.read_text() == "Hello, World!"

    # Verify interactions
    expected_prompt = (
        "Action 1/1: create_file\n  file_path: {}\n  content: Hello, World!".format(
            test_file
        )
    )
    mock_console_interactor_class.confirm_action.assert_called_once_with(
        expected_prompt
    )

    # Verify final report and clipboard behavior
    assert "Execution report copied to clipboard." in result.stdout
    mock_pyperclip_copy.assert_called_once()

    # Get the actual content passed to the copy mock and parse that.
    copied_content = mock_pyperclip_copy.call_args[0][0]
    report = yaml.safe_load(copied_content)

    assert report["run_summary"]["status"] == "SUCCESS"
    assert len(report["action_logs"]) == 1
    assert report["action_logs"][0]["status"] == "COMPLETED"


def test_execute_skip_with_reason_is_reported(
    mock_pyperclip_paste: MagicMock,
    mock_pyperclip_copy: MagicMock,
    mock_console_interactor_class: MagicMock,
    tmp_path: Path,
):
    """
    Scenario 3: Skipping an Action
    - Given I am prompted to approve an action.
    - When I respond with `n`.
    - And I provide the optional reason "Manual check needed".
    - Then the final execution report must show that action with a `SKIPPED`
      status and include the reason "Manual check needed".
    """
    # Arrange
    test_file = tmp_path / "test.txt"
    plan_content = [
        {
            "action": "create_file",
            "params": {"file_path": str(test_file)},
        },
    ]
    plan_yaml = yaml.dump(plan_content)
    mock_pyperclip_paste.return_value = plan_yaml

    # Simulate the user denying and providing a reason
    mock_console_interactor_class.confirm_action.return_value = (
        False,
        "Manual check needed",
    )

    # Act
    action_factory = ActionFactory()
    plan_service = PlanService(
        shell_executor=MagicMock(),
        file_system_manager=LocalFileSystemAdapter(),
        web_scraper=MagicMock(),
        action_factory=action_factory,
        user_interactor=mock_console_interactor_class,
        web_searcher=MagicMock(),
    )
    services = {"plan_service": plan_service, "context_service": MagicMock()}
    result = runner.invoke(app, ["execute"], obj=services, catch_exceptions=False)

    # Assert
    assert result.exit_code == 0
    assert not test_file.exists()
    assert "Execution report copied to clipboard." in result.stdout

    mock_pyperclip_copy.assert_called_once()

    # Get the actual content passed to the copy mock and parse that.
    copied_content = mock_pyperclip_copy.call_args[0][0]
    report = yaml.safe_load(copied_content)

    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SKIPPED"
    assert action_log["reason"] == "Manual check needed"
