import yaml
from teddy.adapters.inbound.cli_formatter import format_report_as_yaml
from teddy.core.domain.models import (
    ExecutionReport,
    ActionResult,
    ExecuteAction,
    CreateFileAction,
)


def test_format_report_with_successful_action():
    """
    Tests that a successful action is formatted correctly in YAML.
    """
    # Arrange
    action = ExecuteAction(command="echo hi")
    report = ExecutionReport(
        run_summary={"status": "SUCCESS"},
        action_logs=[ActionResult(action=action, status="SUCCESS", output="hi")],
    )

    # Act
    yaml_string = format_report_as_yaml(report)

    # Assert
    data = yaml.safe_load(yaml_string)
    log = data["action_logs"][0]
    assert log["status"] == "SUCCESS"
    assert log["output"] == "hi"
    assert log["action"]["type"] == "execute"


def test_format_report_with_failed_action_and_output():
    """
    Tests that a failed action with supplementary output is formatted correctly.
    """
    # Arrange
    error_message = "File already exists"
    output_content = "original file content"
    failed_action = CreateFileAction(file_path="a.txt")
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
    yaml_string = format_report_as_yaml(report)

    # Assert
    data = yaml.safe_load(yaml_string)
    assert data["run_summary"]["status"] == "FAILURE"
    log = data["action_logs"][0]
    assert log["status"] == "FAILURE"
    assert log["error"] == error_message
    assert log["output"] == output_content
    assert log["action"]["type"] == "create_file"


def test_format_report_with_failed_action():
    """
    Tests that a failed action is formatted correctly, showing status and error.
    """
    # Arrange
    error_message = "File already exists"
    failed_action = CreateFileAction(file_path="a.txt")
    report = ExecutionReport(
        run_summary={"status": "FAILURE"},
        action_logs=[
            ActionResult(action=failed_action, status="FAILURE", error=error_message)
        ],
    )

    # Act
    yaml_string = format_report_as_yaml(report)

    # Assert
    data = yaml.safe_load(yaml_string)
    log = data["action_logs"][0]
    assert log["status"] == "FAILURE"
    assert log["error"] == error_message
    assert log["output"] is None
