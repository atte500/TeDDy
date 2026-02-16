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


def test_create_fails_if_file_exists(monkeypatch, tmp_path: Path):
    """
    Given a plan to CREATE a file that already exists,
    When teddy execute is run,
    Then it should fail with a validation error.
    """
    # Arrange
    existing_file = tmp_path / "existing.txt"
    existing_file.write_text("content")

    builder = MarkdownPlanBuilder("Test Create Existing")
    builder.add_action(
        "CREATE",
        params={
            "File Path": f"[{existing_file.name}](/{existing_file.name})",
            "Description": "Overwrite",
        },
        content_blocks={"": ("text", "new content")},
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code != 0
    assert "File already exists" in result.output


def test_edit_fails_if_file_missing(monkeypatch, tmp_path: Path):
    """
    Given a plan to EDIT a file that does not exist,
    When teddy execute is run,
    Then it should fail with a validation error.
    """
    # Arrange
    builder = MarkdownPlanBuilder("Test Edit Missing")
    builder.add_action(
        "EDIT",
        params={
            "File Path": "[missing.txt](/missing.txt)",
            "Description": "Edit missing",
        },
        content_blocks={"`FIND:`": ("text", "foo"), "`REPLACE:`": ("text", "bar")},
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code != 0
    assert "File to edit does not exist" in result.output
