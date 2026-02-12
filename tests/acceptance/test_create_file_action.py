from pathlib import Path
from .helpers import parse_yaml_report, run_cli_with_markdown_plan_on_clipboard
from .plan_builder import MarkdownPlanBuilder


def test_create_file_happy_path(monkeypatch, tmp_path: Path):
    """
    Given a Markdown plan to create a new file,
    When the user executes the plan,
    Then the file should be created with the correct content and the report is valid.
    """
    # Arrange
    file_name = "new_file.txt"
    new_file_path = tmp_path / file_name
    file_content = "Hello, World!"

    builder = MarkdownPlanBuilder("Test Create File")
    builder.add_action(
        "CREATE",
        params={
            "File Path": f"[{file_name}](/{file_name})",
            "Description": "Create a test file.",
        },
        content_blocks={"": ("text", file_content)},
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code == 0, f"Teddy failed with stderr: {result.stderr}"
    assert new_file_path.exists(), "The new file was not created."
    assert new_file_path.read_text() == file_content, "The file content is incorrect."

    # Verify the report output
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"


def test_create_file_when_file_exists_fails_gracefully(monkeypatch, tmp_path: Path):
    """
    Given a file that already exists,
    When a plan is executed to create the same file,
    Then the action should fail, the original file should be unchanged,
    and the report should indicate the failure.
    """
    # Arrange
    existing_file = tmp_path / "existing.txt"
    original_content = "Original content"
    existing_file.write_text(original_content)

    builder = MarkdownPlanBuilder("Test Create on Existing File")
    builder.add_action(
        "CREATE",
        params={
            "File Path": f"[{existing_file.name}](/{existing_file.name})",
            "Description": "Attempt to create an existing file.",
        },
        content_blocks={"": ("text", "New content")},
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code == 1, (
        "Teddy should exit with a non-zero code on plan failure"
    )
    assert existing_file.read_text() == original_content

    # The report should clearly indicate the failure
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "FAILURE"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"

    details = action_log["details"]
    # Handle both old string format (if any) and new dict format
    if isinstance(details, dict):
        error_msg = details.get("original_details", str(details))
    else:
        error_msg = str(details)
    assert "File exists" in str(error_msg)
