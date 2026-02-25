from .helpers import run_cli_with_markdown_plan_on_clipboard, parse_markdown_report
from .plan_builder import MarkdownPlanBuilder


def test_parser_rejects_improperly_nested_code_fences(monkeypatch, tmp_path):
    """
    Given a markdown plan with an improperly nested code block,
    When the plan is parsed,
    Then the parser must reject it with a clear error.
    (Scenario 1 from slice 10-fix-parser-nesting-bug)
    """
    # This plan is invalid because the inner markdown block uses ```
    # which is the same as the outer fence for the CREATE action's content.
    plan_content = """
# Plan to Create a Failing Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan

### `CREATE`
- **File Path:** failing_plan.md
- **Description:** Create a plan that has invalid nesting.
```markdown
# This is the inner plan that will be created

## Action Plan
### `EXECUTE`
- **Description:** A command.
```shell
echo "hello"
```
```
"""
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    assert result.exit_code != 0
    assert "Execution Report: Invalid Plan" in result.stdout
    assert "- **Overall Status:** Validation Failed" in result.stdout
    assert (
        "Plan structure is invalid. Expected a Level 3 Action Heading" in result.stdout
    )


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
