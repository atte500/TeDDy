from .helpers import parse_yaml_report, run_cli_with_markdown_plan_on_clipboard
from .plan_builder import MarkdownPlanBuilder


def test_successful_execution(monkeypatch, tmp_path):
    """
    Given a valid Markdown plan with a single 'echo' command,
    When the plan is run via the CLI,
    Then the command should exit with status 0,
    And the report should show SUCCESS with the correct output.
    """
    # ARRANGE
    builder = MarkdownPlanBuilder("Test Successful Execution")
    builder.add_action(
        "EXECUTE",
        params={"Description": "Echo hello world."},
        content_blocks={"COMMAND": ("shell", 'echo "hello world"')},
    )
    plan_content = builder.build()

    # ACT
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # ASSERT
    assert result.exit_code == 0, (
        f"Teddy should exit with 0 on success. Output: {result.stdout}"
    )

    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"
    details_dict = action_log["details"]
    assert "hello world" in details_dict.get("stdout", "")


def test_failed_execution(monkeypatch, tmp_path):
    """
    Given a valid Markdown plan with a failing command,
    When the plan is run via the CLI,
    Then the command should exit with a non-zero code,
    And the report should show FAILURE with the correct error output.
    """
    # ARRANGE
    builder = MarkdownPlanBuilder("Test Failed Execution")
    builder.add_action(
        "EXECUTE",
        params={"Description": "Run a non-existent command."},
        content_blocks={"COMMAND": ("shell", "nonexistentcommand12345")},
    )
    plan_content = builder.build()

    # ACT
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # ASSERT
    assert result.exit_code == 1, "Teddy should exit with 1 on failure"

    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "FAILURE"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"

    details_dict = action_log["details"]
    error_msg = details_dict.get("stderr", "").lower()
    assert (
        "not found" in error_msg
        or "no such file" in error_msg
        or "not recognized" in error_msg
    )
