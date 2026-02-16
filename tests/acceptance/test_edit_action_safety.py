from pathlib import Path
from .helpers import parse_markdown_report, run_cli_with_markdown_plan_on_clipboard
from .plan_builder import MarkdownPlanBuilder


def test_edit_action_fails_on_multiple_occurrences(monkeypatch, tmp_path: Path):
    """
    Given a file with multiple occurrences of the find string,
    When an edit action is executed,
    Then the action should fail to prevent ambiguity.
    """
    # Arrange
    file_to_edit = tmp_path / "test.txt"
    original_content = "hello world, hello again"
    file_to_edit.write_text(original_content, encoding="utf-8")

    builder = MarkdownPlanBuilder("Test Ambiguous Edit")
    builder.add_action(
        "EDIT",
        params={
            "File Path": f"[{file_to_edit.name}](/{file_to_edit.name})",
            "Description": "An ambiguous edit.",
        },
        content_blocks={
            "`FIND:`": ("text", "hello"),
            "`REPLACE:`": ("text", "goodbye"),
        },
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code == 1
    assert file_to_edit.read_text() == original_content  # File should be unchanged

    report = parse_markdown_report(result.stdout)
    # Validation failure occurs before execution
    assert report["run_summary"]["Overall Status"] == "Validation Failed"
    # Verify the error message is present
    assert "The `FIND` block is ambiguous" in result.stdout
