from pathlib import Path
from .helpers import run_cli_with_markdown_plan_on_clipboard
from .plan_builder import MarkdownPlanBuilder


def test_plan_fails_with_unknown_action(monkeypatch, tmp_path: Path):
    """
    Given a plan with an unknown action type,
    When teddy execute is run,
    Then it should fail with a validation error stating the action is unknown.
    """
    # Arrange
    builder = MarkdownPlanBuilder("Test Unknown Action")
    # Add a valid action first to ensure the plan isn't empty
    builder.add_action(
        "EXECUTE",
        params={"Description": "Valid"},
        content_blocks={"COMMAND": ("bash", "echo hi")},
    )
    # Add the unknown action
    builder.add_action("UNKNOWN_ACTION", params={"Description": "This should fail"})

    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code != 0, "CLI should have failed due to unknown action."
    # Check result.output to capture both stdout and stderr (where the error message is likely printed)
    assert "Unknown action type: UNKNOWN_ACTION" in result.output
