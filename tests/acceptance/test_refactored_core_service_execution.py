from pathlib import Path

from .helpers import parse_markdown_report, run_cli_with_markdown_plan_on_clipboard
from .plan_builder import MarkdownPlanBuilder


def test_successful_plan_execution_with_refactored_services(
    monkeypatch, tmp_path: Path
):
    """
    Given a valid plan,
    When the user runs the executor,
    Then the new service layer should execute the plan successfully.
    """
    # Arrange
    target_file = tmp_path / "hello.txt"
    file_content = "Hello, World!"

    builder = MarkdownPlanBuilder("Test Core Service Execution")
    builder.add_action(
        "CREATE",
        params={
            "File Path": f"[{target_file.name}](/{target_file.name})",
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
    assert result.exit_code == 0
    assert target_file.exists()
    assert target_file.read_text() == file_content

    report = parse_markdown_report(result.stdout)
    assert report["run_summary"]["Overall Status"] == "SUCCESS"
    assert report["action_logs"][0]["status"] == "SUCCESS"
