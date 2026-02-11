import os
import uuid
from pathlib import Path

from typer.testing import CliRunner

from teddy_executor.main import app
from .plan_builder import MarkdownPlanBuilder

runner = CliRunner()


def test_execute_action_can_see_file_from_create_action(tmp_path: Path):
    """
    Spike to validate filesystem visibility between actions.
    This test simulates a plan that first creates a file and then
    executes a command to read that file's content.
    """
    # 1. Arrange
    test_file_name = f"test_{uuid.uuid4()}.txt"
    test_content = "Hello from the spike!"
    test_file_path = tmp_path / test_file_name

    builder = MarkdownPlanBuilder("Test Plan: Create then Read")
    builder.add_action(
        "CREATE",
        params={
            "File Path": str(test_file_path),
            "Description": "Create a test file.",
        },
        content_blocks={"": ("text", test_content)},
    ).add_action(
        "EXECUTE",
        params={
            "Description": "Read the content of the newly created file using 'cat'."
        },
        content_blocks={"`COMMAND:`": ("shell", f"cat {test_file_path}")},
    )
    plan_content = builder.build()

    # 2. Act
    # Add a pre-condition assertion to guarantee the file does not exist before the run.
    # This directly addresses the risk of a contaminated test environment.
    assert not test_file_path.exists(), (
        f"Pre-condition failed: File {test_file_path} already exists."
    )

    # Use the --plan-content option to inject the plan directly.
    # We must also change the CWD to a temporary directory to isolate the test.
    # Note: chdir is a safe operation for tests as pytest isolates them.
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        result = runner.invoke(
            app,
            ["execute", "-y", "--plan-content", plan_content],
            catch_exceptions=False,
        )
    finally:
        os.chdir(original_cwd)

    # 3. Assert
    assert result.exit_code == 0, (
        f"CLI command failed with exit code {result.exit_code}: {result.stdout}"
    )

    # Parse the report into a Python dictionary for robust assertions.
    from .helpers import parse_yaml_report

    report = parse_yaml_report(result.stdout)
    assert report is not None, "Report output is not valid."

    action_logs = report.get("action_logs", [])
    assert len(action_logs) == 2, "Expected two action logs in the report."

    # Check the CREATE action log
    create_log = action_logs[0]
    assert create_log["status"] == "SUCCESS"
    assert create_log["action_type"] == "CREATE"

    # Check the EXECUTE action log
    execute_log = action_logs[1]
    assert execute_log["status"] == "SUCCESS"
    assert execute_log["action_type"] == "EXECUTE"
    assert execute_log["params"]["command"].strip() == f"cat {test_file_path}"

    # This is the key assertion: verify the stdout of the shell command.
    # The .strip() is important as shell output often has trailing newlines.
    command_stdout = execute_log["details"]["stdout"].strip()
    assert command_stdout == test_content
