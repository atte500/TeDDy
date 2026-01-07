from unittest.mock import MagicMock
from typer.testing import CliRunner

# Import the app object from the refactored module
from teddy.main import app
from teddy.core.domain.models import ExecutionReport
from teddy.core.ports.inbound.run_plan_use_case import RunPlanUseCase

runner = CliRunner()


def test_cli_invokes_use_case_with_stdin_content():
    """
    Tests that the CLI correctly captures stdin and calls the use case.
    """
    # ARRANGE
    # Create a mock implementation of the port
    mock_use_case = MagicMock(spec=RunPlanUseCase)
    # Configure the mock to return a valid, empty report
    mock_use_case.execute.return_value = ExecutionReport(
        run_summary={"status": "SUCCESS"}
    )
    plan_input = "plan content from stdin"

    # ACT
    # Run the CLI command, passing the mock service as the context object `obj`
    # and the plan content as stdin.
    result = runner.invoke(
        app,
        obj={"plan_service": mock_use_case},
        input=plan_input,
        catch_exceptions=False,
    )

    # ASSERT
    # Ensure the CLI command itself succeeded
    assert (
        result.exit_code == 0
    ), f"CLI exited with code {result.exit_code}\n{result.stdout}\n{result.stderr}"

    # Verify that the core use case was called correctly with the content from stdin
    mock_use_case.execute.assert_called_once_with(plan_input)


def test_cli_exits_with_error_code_on_failure():
    """
    Tests that the CLI exits with a non-zero code if the
    execution report indicates a failure.
    """
    # ARRANGE
    mock_use_case = MagicMock(spec=RunPlanUseCase)
    failure_report = ExecutionReport(run_summary={"status": "FAILURE"})
    mock_use_case.execute.return_value = failure_report
    plan_input = "any plan that will fail"

    # ACT
    result = runner.invoke(
        app,
        obj={"plan_service": mock_use_case},
        input=plan_input,
        catch_exceptions=False,
    )

    # ASSERT
    assert (
        result.exit_code == 1
    ), f"CLI should exit with code 1 on failure, but got {result.exit_code}"


def test_cli_handles_create_file_action():
    """
    Tests that the CLI correctly handles a create_file action plan.
    """
    # ARRANGE
    mock_use_case = MagicMock(spec=RunPlanUseCase)
    # Configure the mock to return a valid, empty report
    mock_use_case.execute.return_value = ExecutionReport(
        run_summary={"status": "SUCCESS"}
    )
    plan_yaml = """
    - action: create_file
      params:
        file_path: "test.txt"
        content: "hello"
    """

    # ACT
    result = runner.invoke(
        app,
        obj={"plan_service": mock_use_case},
        input=plan_yaml,
        catch_exceptions=False,
    )

    # ASSERT
    assert (
        result.exit_code == 0
    ), f"CLI exited with code {result.exit_code}\n{result.stdout}\n{result.stderr}"
    mock_use_case.execute.assert_called_once_with(plan_yaml)
