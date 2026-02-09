import sys
from pathlib import Path
import yaml
from typer.testing import CliRunner

from teddy_executor.main import app

runner = CliRunner()


def test_shell_adapter_handles_wildcards_on_posix():
    """
    Verify that the shell adapter can execute commands with wildcards (globbing).
    This is a POSIX-specific feature test.
    """
    if sys.platform == "win32":
        return  # This feature is for POSIX shells

    # GIVEN: A file exists that can be matched by a wildcard
    test_file = Path("test_file_for_wildcard.py")
    test_file.touch()

    plan_content = """
    actions:
      - name: list_python_files
        action: execute
        command: "ls *.py"
    """

    try:
        # WHEN: A plan with a wildcard command is executed
        result = runner.invoke(
            app,
            ["execute", "--plan-content", plan_content, "-y"],
            catch_exceptions=False,
        )

        # THEN: The command succeeds and the output contains the filename
        assert result.exit_code == 0

        # Parse the YAML output to make assertions resilient
        report = yaml.safe_load(result.stdout)
        assert report["run_summary"]["status"] == "SUCCESS"
        action_log = report["action_logs"][0]
        assert action_log["status"] == "SUCCESS"
        assert action_log["params"]["name"] == "list_python_files"
        assert test_file.name in action_log["details"]["stdout"]

    finally:
        # Clean up the created file
        if test_file.exists():
            test_file.unlink()


def test_shell_adapter_handles_pipes_on_posix():
    """
    Verify that the shell adapter can execute commands with pipes.
    This is a POSIX-specific feature test.
    """
    if sys.platform == "win32":
        return  # This feature is for POSIX shells

    plan_content = """
    actions:
      - name: pipe_command
        action: execute
        command: 'echo "hello world" | grep "world"'
    """

    # WHEN: A plan with a pipe command is executed
    result = runner.invoke(
        app,
        ["execute", "--plan-content", plan_content, "-y"],
        catch_exceptions=False,
    )

    # THEN: The command succeeds and the output is correct
    assert result.exit_code == 0
    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"
    assert "hello world" in action_log["details"]["stdout"]
