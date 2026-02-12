from .helpers import run_cli_with_markdown_plan_on_clipboard, parse_markdown_report
from .plan_builder import MarkdownPlanBuilder


def test_markdown_parsing_of_execute_action(monkeypatch, tmp_path):
    """
    Given a markdown plan with an execute action,
    When the plan is run,
    Then it should execute successfully.
    This replaces the legacy YAML colon test with a modern markdown equivalent.
    """
    builder = MarkdownPlanBuilder("Test Execute Action")
    builder.add_action(
        "EXECUTE",
        params={"Description": "Run a command with a colon."},
        content_blocks={"COMMAND": ("shell", "echo hello:world")},
    )
    plan_content = builder.build()

    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    assert result.exit_code == 0
    assert "hello:world" in result.stdout

    report = parse_markdown_report(result.stdout)
    assert report["run_summary"]["Overall Status"] == "SUCCESS"
