from pathlib import Path
from .helpers import parse_markdown_report, run_cli_with_markdown_plan_on_clipboard
from .plan_builder import MarkdownPlanBuilder


def test_read_action_happy_path(monkeypatch, tmp_path: Path):
    """
    Given an existing file,
    When a 'read' action is executed,
    Then the action log's 'details' should contain the file's content.
    """
    # Arrange
    file_content = "Hello, this is the content."
    file_to_read = tmp_path / "readable.txt"
    file_to_read.write_text(file_content, encoding="utf-8")

    builder = MarkdownPlanBuilder("Test Read Action")
    builder.add_action(
        "READ",
        params={
            "Resource": f"[{file_to_read.name}](/{file_to_read.name})",
            "Description": "Read a test file.",
        },
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code == 0
    report = parse_markdown_report(result.stdout)
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"

    # The contract for a successful read is the Resource Contents section
    assert "## Resource Contents" in result.stdout
    assert file_content in result.stdout


def test_read_action_file_not_found(monkeypatch, tmp_path: Path):
    """
    Given a non-existent file path,
    When a 'read' action is executed,
    Then the action should fail and the report should indicate the error.
    """
    # Arrange
    non_existent_file = tmp_path / "non_existent.txt"
    builder = MarkdownPlanBuilder("Test Read Non-Existent File")
    builder.add_action(
        "READ",
        params={
            "Resource": f"[{non_existent_file.name}](/{non_existent_file.name})",
            "Description": "Read a non-existent file.",
        },
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code == 1
    report = parse_markdown_report(result.stdout)
    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"
    assert "No such file or directory" in action_log["details"]["error"]
