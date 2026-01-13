import yaml
from teddy_executor.adapters.inbound.cli_formatter import format_report_as_yaml
from teddy_executor.core.domain.models import (
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
    assert "output" not in log


def test_format_report_uses_literal_block_for_multiline_output():
    """
    Tests that a multi-line string in the 'output' field is formatted
    using a YAML literal block scalar (|) for readability.
    """
    # Arrange
    multiline_content = '{\n  "key": "value",\n  "another": "item"\n}'
    action = ExecuteAction(command="cat file.json")
    report = ExecutionReport(
        run_summary={"status": "SUCCESS"},
        action_logs=[
            ActionResult(action=action, status="SUCCESS", output=multiline_content)
        ],
    )

    # Act
    yaml_string = format_report_as_yaml(report)

    # Assert
    # We check the raw string for the literal block indicator
    assert "output: |" in yaml_string
    # We also parse it to ensure it's still valid YAML
    data = yaml.safe_load(yaml_string)
    assert data["action_logs"][0]["output"] == multiline_content
