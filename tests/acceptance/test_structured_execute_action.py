import sys
from pathlib import Path
from .helpers import (
    run_cli_with_markdown_plan_on_clipboard,
    parse_yaml_report,
    parse_markdown_report,
)
from .plan_builder import MarkdownPlanBuilder

# Define platform-agnostic commands
LIST_COMMAND = "dir" if sys.platform == "win32" else "ls -a"
ECHO_COMMAND = f"{sys.executable} -c \"import os; print(os.environ.get('MY_VAR', ''))\""


def test_execute_action_with_custom_cwd(tmp_path: Path, monkeypatch):
    """
    Given a plan with an execute action specifying a cwd,
    When the plan is executed,
    Then the command should run successfully within the specified directory.
    """
    # Arrange
    sub_dir = tmp_path / "sub"
    sub_dir.mkdir()
    unique_file = sub_dir / "unique_file.txt"
    unique_file.touch()

    builder = MarkdownPlanBuilder("Test Execute with CWD")
    builder.add_action(
        "EXECUTE",
        params={"Description": "List files in a subdirectory.", "cwd": "sub"},
        content_blocks={"COMMAND": ("shell", LIST_COMMAND)},
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code == 0
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"
    assert "unique_file.txt" in action_log["details"]["stdout"]


def test_execute_action_with_env_variables(tmp_path: Path, monkeypatch):
    """
    Given a plan with an execute action specifying an env map,
    When the plan is executed,
    Then the command should run successfully with the specified environment variables.
    """
    # Arrange
    expected_value = "hello_world_from_env"
    builder = MarkdownPlanBuilder("Test Execute with Env")
    builder.add_action(
        "EXECUTE",
        params={
            "Description": "Test environment variables.",
            "env": f"- MY_VAR: {expected_value}",
        },
        content_blocks={"COMMAND": ("shell", ECHO_COMMAND)},
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code == 0
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"
    assert expected_value in action_log["details"]["stdout"]


def test_execute_action_fails_with_unsafe_cwd_traversal(tmp_path: Path, monkeypatch):
    """
    Given a plan where `cwd` attempts to traverse outside the project root,
    When the plan is executed,
    Then the action must fail with a clear error message.
    """
    # Arrange
    builder = MarkdownPlanBuilder("Test Unsafe CWD Traversal")
    builder.add_action(
        "EXECUTE",
        params={
            "Description": "This should fail.",
            "command": "echo 'should not run'",
            "cwd": "../..",
        },
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    report = parse_markdown_report(result.stdout)
    # The validator passes, but execution fails, which is also a valid outcome.
    assert report["run_summary"]["Overall Status"] == "FAILURE"
    assert "is outside the project directory" in result.stdout
    assert result.exit_code != 0


def test_execute_action_fails_with_absolute_cwd(tmp_path: Path, monkeypatch):
    """
    Given a plan where `cwd` is an absolute path,
    When the plan is executed,
    Then the action must fail with a clear error message.
    """
    # Arrange
    absolute_path = str(tmp_path.parent)
    builder = MarkdownPlanBuilder("Test Absolute CWD")
    builder.add_action(
        "EXECUTE",
        params={
            "Description": "This should fail.",
            "command": "echo 'should not run'",
            "cwd": absolute_path,
        },
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    report = parse_markdown_report(result.stdout)
    # The validator passes, but execution fails, which is also a valid outcome.
    assert report["run_summary"]["Overall Status"] == "FAILURE"
    assert "is outside the project directory" in result.stdout
    assert result.exit_code != 0


def test_execute_action_with_both_cwd_and_env(tmp_path: Path, monkeypatch):
    """
    Given a plan with an execute action specifying both cwd and env,
    When the plan is executed,
    Then the command should run in the specified directory with the env vars.
    """
    # Arrange
    sub_dir = tmp_path / "sub"
    sub_dir.mkdir()
    expected_value = "secret_message"
    write_command = f"{sys.executable} -c \"import os; f = open('output.txt', 'w'); f.write(os.environ.get('MY_VAR', '')); f.close()\""

    builder = MarkdownPlanBuilder("Test Execute with CWD and Env")
    builder.add_action(
        "EXECUTE",
        params={
            "Description": "Test with both cwd and env.",
            "cwd": "sub",
            "env": f"- MY_VAR: {expected_value}",
        },
        content_blocks={"COMMAND": ("shell", write_command)},
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code == 0
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"

    output_file = sub_dir / "output.txt"
    assert output_file.exists()
    assert output_file.read_text().strip() == expected_value
