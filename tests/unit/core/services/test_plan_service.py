from unittest.mock import MagicMock

# This import will fail
from teddy.core.services.plan_service import PlanService
from teddy.core.ports.outbound.shell_executor import ShellExecutor
from teddy.core.domain.models import CommandResult


def test_plan_service_handles_invalid_yaml():
    """
    Tests that PlanService returns a failure report for malformed YAML.
    """
    # ARRANGE
    mock_shell_executor = MagicMock(spec=ShellExecutor)
    plan_service = PlanService(shell_executor=mock_shell_executor)
    invalid_plan_content = "this is not valid yaml: { oh no"

    # ACT
    report = plan_service.execute(invalid_plan_content)

    # ASSERT
    mock_shell_executor.run.assert_not_called()
    assert len(report.action_logs) == 1
    action_result = report.action_logs[0]
    assert action_result.status == "FAILURE"
    assert "Failed to process plan" in action_result.error
    assert action_result.action.action_type == "parse_plan"


def test_plan_service_populates_run_summary():
    """
    Tests that PlanService correctly populates the run_summary in the report.
    """
    # ARRANGE
    mock_shell_executor = MagicMock(spec=ShellExecutor)
    # Simulate one success and one failure
    mock_shell_executor.run.side_effect = [
        CommandResult(stdout="ok", stderr="", return_code=0),
        CommandResult(stdout="", stderr="error", return_code=1),
    ]
    plan_service = PlanService(shell_executor=mock_shell_executor)
    plan_content = """
    - { action: execute, params: { command: "true" } }
    - { action: execute, params: { command: "false" } }
    """

    # ACT
    report = plan_service.execute(plan_content)

    # ASSERT
    assert report.run_summary.get("status") == "FAILURE"

    # Test the SUCCESS case
    mock_shell_executor.run.side_effect = [
        CommandResult(stdout="ok", stderr="", return_code=0)
    ]
    plan_content_success = """
    - { action: execute, params: { command: "true" } }
    """
    report_success = plan_service.execute(plan_content_success)
    assert report_success.run_summary.get("status") == "SUCCESS"


def test_plan_service_parses_and_executes_plan():
    """
    Tests that PlanService can parse a valid YAML plan and call the shell executor.
    """
    # ARRANGE
    # 1. Mock the outbound port (ShellExecutor)
    mock_shell_executor = MagicMock(spec=ShellExecutor)
    mock_shell_executor.run.return_value = CommandResult(
        stdout="hello world", stderr="", return_code=0
    )

    # 2. Instantiate the service with the mock dependency
    plan_service = PlanService(shell_executor=mock_shell_executor)

    # 3. Define the input YAML
    plan_content = """
    - action: execute
      params:
        command: echo "hello world"
    """

    # ACT
    report = plan_service.execute(plan_content)

    # ASSERT
    # 1. Assert the outbound port was called correctly
    mock_shell_executor.run.assert_called_once_with('echo "hello world"')

    # 2. Assert the report contains the correct information
    assert len(report.action_logs) == 1
    action_result = report.action_logs[0]
    assert action_result.status == "SUCCESS"
    assert action_result.output == "hello world"
    assert action_result.action.action_type == "execute"
