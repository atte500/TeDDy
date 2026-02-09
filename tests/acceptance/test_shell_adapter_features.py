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


def test_shell_adapter_handles_env_vars_on_posix(monkeypatch):
    """
    Verify that the shell adapter can execute commands with environment variable expansion.
    This is a POSIX-specific feature test.
    """
    if sys.platform == "win32":
        return  # This feature is for POSIX shells

    # GIVEN: an environment variable is set
    monkeypatch.setenv("TEDDY_TEST_VAR", "SUCCESS_VAR")

    plan_content = """
    actions:
      - name: env_var_command
        action: execute
        command: 'echo $TEDDY_TEST_VAR'
    """

    # WHEN: A plan that uses the env var is executed
    result = runner.invoke(
        app,
        ["execute", "--plan-content", plan_content, "-y"],
        catch_exceptions=False,
    )

    # THEN: The command succeeds and the output contains the expanded variable
    assert result.exit_code == 0
    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"
    assert "SUCCESS_VAR" in action_log["details"]["stdout"]


def test_shell_adapter_handles_simple_command_on_posix():
    """
    Verify that the shell adapter still handles simple commands without shell features.
    This is a POSIX-specific feature test.
    """
    if sys.platform == "win32":
        return  # This feature is for POSIX shells

    # GIVEN: a directory exists
    test_dir = Path("test_dir_for_simple_command")
    test_dir.mkdir()

    plan_content = f"""
    actions:
      - name: simple_ls
        action: execute
        command: 'ls -d {test_dir.name}'
    """

    try:
        # WHEN: A plan with a simple command is executed
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
        assert test_dir.name in action_log["details"]["stdout"]
    finally:
        if test_dir.exists():
            test_dir.rmdir()
