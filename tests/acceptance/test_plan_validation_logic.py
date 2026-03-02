from pathlib import Path
from .helpers import run_cli_with_markdown_plan_on_clipboard
from .plan_builder import MarkdownPlanBuilder


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


def test_execute_action_with_multiple_commands_fails_validation(
    monkeypatch, tmp_path: Path
):
    """
    Given a plan with an EXECUTE action containing multiple command lines,
    When teddy execute is run,
    Then it should fail with a validation error.
    """
    # Arrange
    builder = MarkdownPlanBuilder("Test Execute Multiline")
    builder.add_action(
        "EXECUTE",
        params={"Description": "A multiline command"},
        content_blocks={"": ("shell", 'echo "hello"\necho "world"')},
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code != 0
    assert "Validation Error" in result.output
    assert "EXECUTE action must contain exactly one command" in result.output


def test_execute_action_with_chained_command_fails_validation(
    monkeypatch, tmp_path: Path
):
    """
    Given a plan with an EXECUTE action containing a chained command (&&),
    When teddy execute is run,
    Then it should fail with a validation error.
    """
    # Arrange
    builder = MarkdownPlanBuilder("Test Execute Chained")
    builder.add_action(
        "EXECUTE",
        params={"Description": "A chained command"},
        content_blocks={"": ("shell", 'echo "hello" && echo "world"')},
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code != 0
    assert "Validation Error" in result.output
    assert "Command chaining with '&&' is not allowed" in result.output
