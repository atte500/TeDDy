from pathlib import Path
from unittest.mock import MagicMock, patch
import yaml
from typer.testing import CliRunner

from teddy_executor.main import app, create_container
from teddy_executor.core.ports.outbound import IUserInteractor
from teddy_executor.core.services.action_dispatcher import ActionDispatcher
from teddy_executor.core.domain.models import ActionLog, ActionStatus

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
    _, call_kwargs = mock_interactor.confirm_action.call_args
    prompt_message = call_kwargs["action_prompt"]
    assert "Create a test file for the QoL feature." in prompt_message


def test_chat_with_user_skips_approval_prompt(tmp_path: Path):
    """
    Given a plan with a 'chat_with_user' action,
    When the plan is run in interactive mode,
    Then the approval prompt should be skipped and the action dispatched directly.
    """
    # Arrange
    runner = CliRunner(mix_stderr=False)
    plan_structure = [{"action": "chat_with_user", "params": {"prompt": "Hello?"}}]
    plan_yaml = yaml.dump(plan_structure)
    plan_file = tmp_path / "plan.yaml"
    plan_file.write_text(plan_yaml)

    mock_interactor = MagicMock(spec=IUserInteractor)
    # Configure confirm_action to prevent a ValueError if it's called.
    mock_interactor.confirm_action.return_value = (True, "")
    # The action handler for chat_with_user is the interactor's `ask_question`
    mock_interactor.ask_question.return_value = "World"

    # We also mock the dispatcher to prevent it from trying to create a real
    # action handler, which would be complex to set up. We just need to know
    # that the orchestrator calls it.
    mock_dispatcher = MagicMock(spec=ActionDispatcher)
    mock_dispatcher.dispatch_and_execute.return_value = ActionLog(
        action_type="chat_with_user",
        status=ActionStatus.SUCCESS,
        params={"prompt": "Hello?"},
    )

    test_container = create_container()
    test_container.register(IUserInteractor, instance=mock_interactor)
    test_container.register(ActionDispatcher, instance=mock_dispatcher)

    # Act
    with patch("teddy_executor.main.container", test_container):
        # Run in interactive mode (no --yes flag)
        result = runner.invoke(app, ["execute", str(plan_file)])

    # Assert
    assert result.exit_code == 0
    # The core of the test: `confirm_action` should NOT have been called.
    mock_interactor.confirm_action.assert_not_called()
    # But the action dispatcher should have been called.
    mock_dispatcher.dispatch_and_execute.assert_called_once()


def test_execute_read_on_complex_file_formats_correctly(tmp_path: Path):
    """
    Verifies that reading a complex, multi-line file results in a
    correctly formatted YAML report with a literal block.
    This is a regression test for a bug caused by PyYAML's content-sniffing.
    """
    # Use the main README.md as the complex file input
    plan_content = """
actions:
  - action: read
    path: ../../README.md
"""
    plan_file = tmp_path / "plan.yaml"
    plan_file.write_text(plan_content)

    result = runner.invoke(app, ["execute", str(plan_file), "--yes", "--no-copy"])
    assert result.exit_code == 0
    output = result.stdout

    # The most important assertion: check for the literal block indicator.
    assert "content: |" in output
    # Also check that it's not the incorrect, single-line escaped format.
    assert (
        r"# TeDDy: Your Contract-First & Test-Driven Pair-Programmer\n\n" not in output
    )


def test_read_action_report_formats_multiline_content_correctly(tmp_path: Path):
    """
    Verifies that the YAML report for a `read` action correctly formats
    multi-line file content using a literal block scalar. (Regression Test)
    """
    # GIVEN a file with multi-line content
    test_file = tmp_path / "multi_line.txt"
    test_file.write_text("line one\nline two")

    # and a plan to read that file
    plan_file = tmp_path / "plan.yaml"
    plan_file.write_text(f"""
- action: read
  path: '{test_file}'
""")

    real_container = create_container()

    # WHEN the plan is executed
    with patch("teddy_executor.main.container", real_container):
        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

    # THEN the command should succeed
    assert result.exit_code == 0

    # AND the output should contain the correctly formatted multi-line string
    assert "content: |" in result.stdout


def test_read_action_is_formatted_as_literal_block(tmp_path: Path):
    """
    Given a read action on a multi-line file,
    When the execution report is generated,
    Then the file content should be formatted as a YAML literal block.
    """
    # Arrange
    runner = CliRunner(mix_stderr=False)
    file_content = """# TeDDy

This is a paragraph with **bold** text.

- A list item
- Another list item

```python
# A code block
def hello():
    print("Hello")
```
"""
    test_file = tmp_path / "test.txt"
    test_file.write_text(file_content)

    plan_structure = [{"action": "read", "path": str(test_file)}]
    plan_yaml = yaml.dump(plan_structure)
    plan_file = tmp_path / "plan.yml"
    plan_file.write_text(plan_yaml)

    # Use the real container to test the full formatting pipeline
    real_container = create_container()

    # Act
    with patch("teddy_executor.main.container", real_container):
        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

    # Assert
    assert result.exit_code == 0
    # Assert on the raw string output to verify the literal block style
    stdout = result.stdout
    assert "content: |" in stdout
