from datetime import datetime
import yaml

from teddy_executor.adapters.inbound.cli_formatter import format_report_as_yaml
from teddy_executor.core.domain.models import (
    ExecutionReport,
    RunSummary,
    ActionLog,
    RunStatus,
    ActionStatus,
)


def test_format_report_with_successful_action():
    """
    Tests that a successful action is formatted correctly in YAML.
    """
    # Arrange
    report = ExecutionReport(
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(),
            end_time=datetime.now(),
        ),
        action_logs=[
            ActionLog(
                status=ActionStatus.SUCCESS,
                action_type="execute",
                params={"command": "echo hi"},
                details={"stdout": "hi", "stderr": "", "return_code": 0},
            )
        ],
    )

    # Act
    yaml_string = format_report_as_yaml(report)

    # Assert
    data = yaml.safe_load(yaml_string)
    log = data["action_logs"][0]
    assert log["status"] == "SUCCESS"
    assert log["details"]["stdout"] == "hi"
    assert log["action_type"] == "execute"
