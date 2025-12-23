import os
import platform
import yaml
from teddy.adapters.inbound.cli_formatter import format_report_as_yaml
from teddy.core.domain.models import ExecutionReport, ActionResult, ExecuteAction


def test_format_report_as_yaml():
    """
    Given an ExecutionReport object,
    When format_report_as_yaml is called,
    Then it should return a valid YAML string with the correct structure.
    """
    # Arrange
    action = ExecuteAction(command="ls -l")
    action_result = ActionResult(
        action=action,
        status="SUCCESS",
        output="total 0",
        error=None,
    )
    report = ExecutionReport(
        run_summary={"status": "SUCCESS", "duration_seconds": 0.1},
        action_logs=[action_result],
    )

    # Act
    yaml_output = format_report_as_yaml(report)

    # Assert
    # Parse the output to verify it's valid YAML
    data = yaml.safe_load(yaml_output)

    assert data["run_summary"]["status"] == "SUCCESS"
    assert data["environment"]["os"] == platform.system()
    assert data["environment"]["cwd"] == str(os.getcwd())

    assert len(data["action_logs"]) == 1
    log = data["action_logs"][0]
    assert log["action"]["type"] == "execute"
    assert log["action"]["params"]["command"] == "ls -l"
    assert log["status"] == "SUCCESS"
    assert log["output"] == "total 0"
    assert log["error"] is None
