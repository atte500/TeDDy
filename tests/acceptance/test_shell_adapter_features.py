import sys
from pathlib import Path

from .helpers import run_cli_with_markdown_plan_on_clipboard, parse_yaml_report
from .plan_builder import MarkdownPlanBuilder


def test_shell_adapter_handles_wildcards_on_posix(monkeypatch, tmp_path: Path):
    """
    Verify that the shell adapter can execute commands with wildcards (globbing).
    This is a POSIX-specific feature test.
    """
    if sys.platform == "win32":
        return

    test_file = tmp_path / "test_file_for_wildcard.py"
    test_file.touch()

    builder = MarkdownPlanBuilder("Test Wildcard Execution")
    builder.add_action(
        "EXECUTE",
        params={"Description": "List python files using wildcard."},
        content_blocks={"COMMAND": ("shell", "ls *.py")},
    )
    plan_content = builder.build()

    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    assert result.exit_code == 0
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"
    assert test_file.name in action_log["details"]["stdout"]


def test_shell_adapter_handles_pipes_on_posix(monkeypatch, tmp_path: Path):
    """
    Verify that the shell adapter can execute commands with pipes.
    This is a POSIX-specific feature test.
    """
    if sys.platform == "win32":
        return

    builder = MarkdownPlanBuilder("Test Pipe Execution")
    builder.add_action(
        "EXECUTE",
        params={"Description": "Test a piped command."},
        content_blocks={"COMMAND": ("shell", 'echo "hello world" | grep "world"')},
    )
    plan_content = builder.build()

    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    assert result.exit_code == 0
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"
    assert "hello world" in action_log["details"]["stdout"]


def test_shell_adapter_handles_env_vars_on_posix(monkeypatch, tmp_path: Path):
    """
    Verify that the shell adapter can execute commands with environment variable expansion.
    This is a POSIX-specific feature test.
    """
    if sys.platform == "win32":
        return

    monkeypatch.setenv("TEDDY_TEST_VAR", "SUCCESS_VAR")
    builder = MarkdownPlanBuilder("Test Env Var Execution")
    builder.add_action(
        "EXECUTE",
        params={"Description": "Echo an environment variable."},
        content_blocks={"COMMAND": ("shell", "echo $TEDDY_TEST_VAR")},
    )
    plan_content = builder.build()

    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    assert result.exit_code == 0
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"
    assert "SUCCESS_VAR" in action_log["details"]["stdout"]


def test_shell_adapter_handles_simple_command_on_posix(monkeypatch, tmp_path: Path):
    """
    Verify that the shell adapter still handles simple commands without shell features.
    This is a POSIX-specific feature test.
    """
    if sys.platform == "win32":
        return

    test_dir = tmp_path / "test_dir_for_simple_command"
    test_dir.mkdir()

    builder = MarkdownPlanBuilder("Test Simple Command Execution")
    builder.add_action(
        "EXECUTE",
        params={"Description": "Run a simple ls command."},
        content_blocks={"COMMAND": ("shell", f"ls -d {test_dir.name}")},
    )
    plan_content = builder.build()

    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    assert result.exit_code == 0
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"
    assert test_dir.name in action_log["details"]["stdout"]
