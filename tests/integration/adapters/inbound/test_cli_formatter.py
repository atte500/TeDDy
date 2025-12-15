from teddy.adapters.inbound.cli_formatter import format_report_as_markdown
from teddy.core.domain.models import ExecutionReport, ActionResult
from teddy.core.services.action_factory import ActionFactory


def test_format_report_with_successful_action():
    """
    Tests that a successful action is formatted correctly.
    """
    # Arrange
    factory = ActionFactory()
    action = factory.create_action(
        {"action": "execute", "params": {"command": "echo hi"}}
    )
    report = ExecutionReport(
        run_summary={"status": "SUCCESS"},
        action_logs=[ActionResult(action=action, status="SUCCESS", output="hi")],
    )

    # Act
    formatted_string = format_report_as_markdown(report)

    # Assert
    assert "- **Status:** SUCCESS" in formatted_string
    assert "- **Output:**" in formatted_string
    assert "hi" in formatted_string


def test_format_report_with_failed_action_and_output():
    """
    Tests that a failed action with supplementary output (e.g., file content)
    is formatted correctly.
    """
    # Arrange
    factory = ActionFactory()
    error_message = "File already exists"
    output_content = "original file content"
    failed_action = factory.create_action(
        {"action": "create_file", "params": {"file_path": "a.txt"}}
    )
    report = ExecutionReport(
        run_summary={"status": "FAILURE"},
        action_logs=[
            ActionResult(
                action=failed_action,
                status="FAILURE",
                error=error_message,
                output=output_content,
            )
        ],
    )

    # Act
    formatted_string = format_report_as_markdown(report)

    # Assert
    expected_details = """
- **Details:**
  ```yaml
  status: FAILURE
  error: File already exists
  output: |
    original file content
  ```"""
    assert expected_details in formatted_string


def test_format_report_with_failed_action():
    """
    Tests that a failed action is formatted correctly, showing status and error.
    """
    # Arrange
    factory = ActionFactory()
    error_message = "File already exists"
    failed_action = factory.create_action(
        {"action": "create_file", "params": {"file_path": "a.txt"}}
    )
    report = ExecutionReport(
        run_summary={"status": "FAILURE"},
        action_logs=[
            ActionResult(action=failed_action, status="FAILURE", error=error_message)
        ],
    )

    # Act
    formatted_string = format_report_as_markdown(report)

    # Assert
    expected_details = """
- **Details:**
  ```yaml
  status: FAILURE
  error: File already exists
  ```"""
    assert expected_details in formatted_string
