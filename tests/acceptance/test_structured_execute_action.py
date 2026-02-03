import sys
from pathlib import Path
from unittest.mock import patch
import yaml
from typer.testing import CliRunner

from teddy_executor.main import app, create_container
from tests.acceptance.helpers import (
    run_cli_with_plan,
    parse_yaml_report,
)

# Define platform-agnostic commands
LIST_COMMAND = "dir" if sys.platform == "win32" else "ls -a"
ECHO_COMMAND = "(echo %MY_VAR%)" if sys.platform == "win32" else "echo $MY_VAR"


def test_execute_action_with_custom_cwd(tmp_path: Path, monkeypatch):
    """
    Scenario 2: Command with a Custom Working Directory
    Given a plan with an execute action specifying a cwd
    When the plan is executed
    Then the command should run successfully within the specified directory.
    """
    # Arrange
    # Create a subdirectory and a unique file inside it
    sub_dir = tmp_path / "sub"
    sub_dir.mkdir()
    unique_file = sub_dir / "unique_file.txt"
    unique_file.touch()

    # The plan will execute 'ls -a' (or 'dir') inside the 'sub' directory.
    # We expect to see 'unique_file.txt' in the output.
    plan = [
        {
            "action": "execute",
            "params": {
                "command": LIST_COMMAND,
                "cwd": "sub",
            },
        }
    ]

    # Act
    result = run_cli_with_plan(monkeypatch, plan, cwd=tmp_path)

    # Assert
    assert result.exit_code == 0
    report = parse_yaml_report(result.stdout)

    # Check that the overall run was successful
    assert report["run_summary"]["status"] == "SUCCESS"

    # Check that the command output contains the unique file, proving it ran in the correct directory
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"
    assert "unique_file.txt" in action_log["details"]["stdout"]


def test_execute_action_with_env_variables(tmp_path: Path, monkeypatch):
    """
    Scenario 3: Command with Environment Variables
    Given a plan with an execute action specifying an env map
    When the plan is executed
    Then the command should run successfully with the specified environment variables.
    """
    # Arrange
    expected_value = "hello_world_from_env"
    plan = [
        {
            "action": "execute",
            "params": {
                "command": ECHO_COMMAND,
                "env": {"MY_VAR": expected_value},
            },
        }
    ]

    # Act
    result = run_cli_with_plan(monkeypatch, plan, cwd=tmp_path)

    # Assert
    assert result.exit_code == 0
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"
    assert expected_value in action_log["details"]["stdout"]


def test_execute_action_fails_with_unsafe_cwd_traversal(tmp_path: Path):
    """
    Scenario 6: Attempting to Use an Unsafe `cwd` Path (Traversal)
    Given a plan where `cwd` attempts to traverse outside the project root
    When the plan is executed
    Then the action must fail with a clear error message.
    """
    # Arrange
    plan = [
        {
            "action": "execute",
            "params": {
                "command": "echo 'should not run'",
                "cwd": "../..",
            },
        }
    ]

    # Act
    runner = CliRunner()
    plan_content = yaml.dump(plan)
    plan_file = tmp_path / "plan.yml"
    plan_file.write_text(plan_content)
    real_container = create_container()

    with patch("teddy_executor.main.container", real_container):
        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

    # Assert
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "FAILURE"
    error_log = report["action_logs"][0]
    assert error_log["status"] == "FAILURE"
    assert "is outside the project directory" in error_log["details"]
    assert result.exit_code != 0


def test_execute_action_fails_with_absolute_cwd(tmp_path: Path):
    """
    Scenario 6: Attempting to Use an Unsafe `cwd` Path (Absolute)
    Given a plan where `cwd` is an absolute path
    When the plan is executed
    Then the action must fail with a clear error message.
    """
    # Arrange
    # Use the parent of the temp path as an example of an absolute path
    # that is also outside the project root for this test.
    absolute_path = str(tmp_path.parent)
    plan = [
        {
            "action": "execute",
            "params": {
                "command": "echo 'should not run'",
                "cwd": absolute_path,
            },
        }
    ]

    # Act
    runner = CliRunner()
    plan_content = yaml.dump(plan)
    plan_file = tmp_path / "plan.yml"
    plan_file.write_text(plan_content)
    real_container = create_container()

    with patch("teddy_executor.main.container", real_container):
        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

    # Assert
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "FAILURE"
    error_log = report["action_logs"][0]
    assert error_log["status"] == "FAILURE"
    assert "Validation failed" in error_log["details"]
    assert "must be relative" in error_log["details"]
    assert result.exit_code != 0


def test_execute_action_backwards_compatibility(tmp_path: Path, monkeypatch):
    """
    Scenario 5: Backwards Compatibility (Simple String Command)
    Given a plan where the execute action is a simple string (old format)
    When the plan is executed
    Then the executor should interpret it as a command with no cwd or env.
    """
    # Arrange
    plan = [{"action": "execute", "params": "echo 'it works'"}]

    # Act
    result = run_cli_with_plan(monkeypatch, plan, cwd=tmp_path)

    # Assert
    assert result.exit_code == 0
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"
    assert "it works" in action_log["details"]["stdout"]


def test_execute_action_with_both_cwd_and_env(tmp_path: Path, monkeypatch):
    """
    Scenario 4: Command with Both `cwd` and `env`
    Given a plan with an execute action specifying both cwd and env
    When the plan is executed
    Then the command should run in the specified directory with the env vars.
    """
    # Arrange
    # Create a subdirectory and a file to write into
    sub_dir = tmp_path / "sub"
    sub_dir.mkdir()
    expected_value = "secret_message"

    # Command to write the env var into a file in the subdir
    write_command = (
        "(echo %MY_VAR% > output.txt)"
        if sys.platform == "win32"
        else "echo $MY_VAR > output.txt"
    )

    plan = [
        {
            "action": "execute",
            "params": {
                "command": write_command,
                "cwd": "sub",
                "env": {"MY_VAR": expected_value},
            },
        }
    ]

    # Act
    result = run_cli_with_plan(monkeypatch, plan, cwd=tmp_path)

    # Assert
    assert result.exit_code == 0
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"

    # Verify that the file was created in the correct directory with the correct content
    output_file = sub_dir / "output.txt"
    assert output_file.exists()
    assert output_file.read_text().strip() == expected_value
