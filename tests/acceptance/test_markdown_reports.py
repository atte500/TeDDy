from pathlib import Path

from .helpers import run_cli_with_markdown_plan_on_clipboard
from .plan_builder import MarkdownPlanBuilder


def test_plan_fails_pre_flight_validation(monkeypatch, tmp_path: Path):
    """
    Given a markdown plan on the clipboard to edit a file with a non-existent FIND block,
    When the user runs `teddy execute`,
    Then the command should fail before executing any actions,
    And the output should be a markdown report detailing the validation failure.
    """
    # Arrange
    file_to_edit = tmp_path / "hello.txt"
    file_to_edit.write_text("Hello, world!")

    builder = MarkdownPlanBuilder("Test Plan: Validation Failure")
    builder.add_action(
        "EDIT",
        params={
            "File Path": file_to_edit.as_posix(),
            "Description": "An edit that should fail validation.",
        },
        content_blocks={
            "`FIND:`": ("text", "Goodbye, world!"),
            "`REPLACE:`": ("text", "Hello, TeDDy!"),
        },
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code == 1, (
        f"Expected exit code 1, but got {result.exit_code}. Output:\\n{result.stdout}"
    )

    # Assert on the Markdown report content using robust parser
    from .helpers import parse_markdown_report

    report = parse_markdown_report(result.stdout)
    assert report["run_summary"].get("Overall Status") == "Validation Failed"

    # Also check for the specific error message text
    assert "## Validation Errors" in result.stdout
    assert "The `FIND` block could not be located in the file" in result.stdout
