from unittest.mock import MagicMock
from typer.testing import CliRunner

# Import the app object from the refactored module
from teddy.main import app
from teddy.core.ports.inbound.run_plan_use_case import RunPlanUseCase

runner = CliRunner()


def test_cli_invokes_use_case_with_stdin_content():
    """
    Tests that the CLI correctly captures stdin and calls the use case.
    """
    # ARRANGE
    # Create a mock implementation of the port
    mock_use_case = MagicMock(spec=RunPlanUseCase)

    plan_input = "plan content from stdin"

    # ACT
    # Run the CLI command, passing the mock service as the context object `obj`
    # and the plan content as stdin.
    result = runner.invoke(
        app, obj=mock_use_case, input=plan_input, catch_exceptions=False
    )

    # ASSERT
    # Ensure the CLI command itself succeeded
    assert (
        result.exit_code == 0
    ), f"CLI exited with code {result.exit_code}\n{result.stdout}\n{result.stderr}"

    # Verify that the core use case was called correctly with the content from stdin
    mock_use_case.execute.assert_called_once_with(plan_input)
