from pathlib import Path

from .helpers import run_cli_with_markdown_plan_on_clipboard, parse_markdown_report
from .plan_builder import MarkdownPlanBuilder


def test_create_file_on_existing_file_fails_and_reports_correctly(
    monkeypatch, tmp_path: Path
):
    """
    Given a file that already exists,
    When a plan is executed to create the same file,
    Then the action should fail, the original file should be unchanged,
    and the report should contain the error message.
    """
    # ARRANGE
    existing_file = tmp_path / "existing.txt"
    original_content = "original content"
    existing_file.write_text(original_content, encoding="utf-8")

    builder = MarkdownPlanBuilder("Test Create on Existing File")
    builder.add_action(
        "CREATE",
        params={
            "File Path": f"[{existing_file.name}](/{existing_file.name})",
            "Description": "A test create action.",
        },
        content_blocks={"": ("text", "This is new content.")},
    )
    plan_content = builder.build()

    # ACT
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # ASSERT
    assert result.exit_code == 1, (
        "Teddy should exit with a non-zero code on plan failure"
    )
    assert existing_file.read_text() == original_content, (
        "The original file should not be modified"
    )

    # Assert on the Markdown report content using robust parser
    report = parse_markdown_report(result.stdout)
    assert report["run_summary"].get("Overall Status") == "FAILURE"

    # Check that the failure detail is present in the output
    assert "File exists:" in result.stdout
