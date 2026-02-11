from pathlib import Path

from .helpers import (
    parse_yaml_report,
    run_cli_with_markdown_plan_on_clipboard,
    parse_markdown_report,
)
from .plan_builder import MarkdownPlanBuilder


def test_edit_action_happy_path(monkeypatch, tmp_path: Path):
    """
    Given a plan to edit an existing file,
    When the plan is executed,
    Then the file content should be updated correctly.
    """
    # Arrange
    file_to_edit = tmp_path / "test_file.txt"
    file_to_edit.write_text("Hello world, this is a test.")

    builder = MarkdownPlanBuilder("Test Edit Action")
    builder.add_action(
        "EDIT",
        params={
            "File Path": f"[{file_to_edit.name}](/{file_to_edit.name})",
            "Description": "Test basic find and replace.",
        },
        content_blocks={"`FIND:`": ("text", "world"), "`REPLACE:`": ("text", "planet")},
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code == 0
    assert file_to_edit.read_text() == "Hello planet, this is a test."

    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    assert report["action_logs"][0]["status"] == "SUCCESS"


def test_edit_action_file_not_found(monkeypatch, tmp_path: Path):
    """
    Given a plan to edit a non-existent file,
    When the plan is executed,
    Then the action should fail and report the error.
    """
    # Arrange
    non_existent_file = tmp_path / "non_existent.txt"
    builder = MarkdownPlanBuilder("Test Edit Non-Existent File")
    builder.add_action(
        "EDIT",
        params={
            "File Path": f"[{non_existent_file.name}](/{non_existent_file.name})",
            "Description": "Test edit on non-existent file.",
        },
        content_blocks={"`FIND:`": ("text", "foo"), "`REPLACE:`": ("text", "bar")},
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code == 1
    report = parse_markdown_report(result.stdout)
    assert report["run_summary"]["Overall Status"] == "Validation Failed"
    assert "File to edit does not exist" in result.stdout
