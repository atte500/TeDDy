from pathlib import Path
from .helpers import parse_markdown_report, run_execute_with_plan_content
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
    result = run_execute_with_plan_content(monkeypatch, plan_content, tmp_path)

    # Assert
    assert result.exit_code == 0, f"Teddy failed with stderr: {result.stderr}"
    assert new_file_path.exists(), "The new file was not created."
    assert new_file_path.read_text() == file_content, "The file content is incorrect."

    # Verify the report output
    report = parse_markdown_report(result.stdout)
    assert report["run_summary"]["Overall Status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"
