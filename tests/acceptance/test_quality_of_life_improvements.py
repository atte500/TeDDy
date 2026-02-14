import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner

from teddy_executor.main import app, create_container
from teddy_executor.core.ports.outbound import IUserInteractor
from teddy_executor.core.services.action_dispatcher import ActionDispatcher
from teddy_executor.core.domain.models import ActionLog, ActionStatus
from tests.acceptance.plan_builder import MarkdownPlanBuilder

runner = CliRunner()


def test_interactive_prompt_shows_description(tmp_path: Path):
    """
    Given a plan with an action that has a 'description' field,
    When the user runs `execute` interactively,
    Then the confirmation prompt should include the description.
    """
    # Arrange
    test_file = tmp_path / "test.txt"
    plan_content = (
        MarkdownPlanBuilder("QoL Test Plan: Description")
        .add_action(
            "create",
            params={
                "File Path": f"[{test_file.name}](/{test_file.name})",
                "Description": "Create a test file for the QoL feature.",
            },
            content_blocks={"": ("text", "hello")},
        )
        .build()
    )

    # Mock the UserInteractor to simulate user approval and capture the prompt
    mock_interactor = MagicMock(spec=IUserInteractor)
    mock_interactor.confirm_action.return_value = (True, "")

    test_container = create_container()
    test_container.register(IUserInteractor, instance=mock_interactor)

    # Act
    # Change CWD to the temp path so file operations in the plan are contained
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        with patch("teddy_executor.main.container", test_container):
            result = runner.invoke(app, ["execute", "--plan-content", plan_content])
    finally:
        os.chdir(original_cwd)

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
    plan_content = (
        MarkdownPlanBuilder("QoL Test Plan: Chat")
        .add_action("chat_with_user", params={"prompt": "Hello?"})
        .build()
    )

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
        action_type="CHAT_WITH_USER",
        status=ActionStatus.SUCCESS,
        params={"prompt": "Hello?"},
    )

    test_container = create_container()
    test_container.register(IUserInteractor, instance=mock_interactor)
    test_container.register(ActionDispatcher, instance=mock_dispatcher)

    # Act
    with patch("teddy_executor.main.container", test_container):
        # Run in interactive mode (no --yes flag)
        result = runner.invoke(app, ["execute", "--plan-content", plan_content])

    # Assert
    assert result.exit_code == 0
    # The core of the test: `confirm_action` should NOT have been called.
    mock_interactor.confirm_action.assert_not_called()
    # But the action dispatcher should have been called.
    mock_dispatcher.dispatch_and_execute.assert_called_once()


def test_read_action_report_formats_multiline_content_correctly(tmp_path: Path):
    """
    Verifies that the Markdown report for a `read` action correctly formats
    multi-line file content. (Regression Test)
    """
    # GIVEN a file with multi-line content
    test_file = tmp_path / "multi_line.txt"
    test_file.write_text("line one\nline two", encoding="utf-8")

    # and a plan to read that file
    plan_content = (
        MarkdownPlanBuilder("QoL Test Plan: Read multiline")
        .add_action(
            "read", params={"Resource": f"[{test_file.name}](/{test_file.name})"}
        )
        .build()
    )

    real_container = create_container()

    # WHEN the plan is executed
    # Change CWD to the temp path so file operations in the plan are contained
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        with patch("teddy_executor.main.container", real_container):
            result = runner.invoke(
                app, ["execute", "--plan-content", plan_content, "--yes"]
            )
    finally:
        os.chdir(original_cwd)

    # THEN the command should succeed
    assert result.exit_code == 0

    # AND the output should contain the content in the report
    assert "line one" in result.stdout
    assert "line two" in result.stdout


def test_read_action_is_formatted_as_literal_block(tmp_path: Path):
    """
    Given a read action on a multi-line file containing markdown,
    When the execution report is generated,
    Then the file content should be correctly included in the report.
    """
    # Arrange
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
    test_file.write_text(file_content, encoding="utf-8")

    plan_content = (
        MarkdownPlanBuilder("QoL Test Plan: Read complex markdown")
        .add_action(
            "read", params={"Resource": f"[{test_file.name}](/{test_file.name})"}
        )
        .build()
    )

    # Use the real container to test the full formatting pipeline
    real_container = create_container()

    # Act
    # Change CWD to the temp path so file operations in the plan are contained
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        with patch("teddy_executor.main.container", real_container):
            result = runner.invoke(
                app, ["execute", "--plan-content", plan_content, "--yes"]
            )
    finally:
        os.chdir(original_cwd)

    # Assert
    assert result.exit_code == 0
    # Assert on the raw string output to verify content is present
    stdout = result.stdout
    assert "def hello():" in stdout
    assert 'print("Hello")' in stdout
