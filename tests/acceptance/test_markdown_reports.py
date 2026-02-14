from pathlib import Path

import re
from typer.testing import CliRunner

from teddy_executor.main import app
from .helpers import parse_markdown_report, run_cli_with_markdown_plan_on_clipboard
from .plan_builder import MarkdownPlanBuilder

runner = CliRunner()


def test_plan_fails_pre_flight_validation(monkeypatch, tmp_path: Path):
    """
    Given a markdown plan on the clipboard to edit a file with a non-existent FIND block,
    When the user runs `teddy execute`,
    Then the command should fail before executing any actions,
    And the output should be a markdown report detailing the validation failure.
    """
    # Arrange
    file_to_edit = tmp_path / "hello.txt"
    file_to_edit.write_text("Hello, world!", encoding="utf-8")

    builder = MarkdownPlanBuilder("Test Plan: Validation Failure")
    builder.add_action(
        "EDIT",
        params={
            "File Path": file_to_edit.name,
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


def test_successful_read_action_includes_content_in_report(monkeypatch, tmp_path: Path):
    """
    Given a valid plan to read a file,
    When the user runs `teddy execute`,
    Then the command should succeed,
    And the final markdown report should contain a "Resource Contents" section
    with the full content of the file that was read.
    """
    # Arrange
    file_to_read = tmp_path / "document.md"
    file_content = "# Hello World\n\nThis is the content."
    file_to_read.write_text(file_content, encoding="utf-8")

    builder = MarkdownPlanBuilder("Test Plan: Read Action")
    builder.add_action(
        "READ",
        params={
            "Resource": file_to_read.name,
            "Description": "Read the document.",
        },
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code == 0, (
        f"Expected exit code 0, but got {result.exit_code}. Output:\\n{result.stdout}"
    )
    assert "## Resource Contents" in result.stdout
    assert file_content in result.stdout


def test_failed_edit_action_includes_file_content_in_report(
    monkeypatch, tmp_path: Path
):
    """
    Given a plan with an EDIT action that fails during execution (not validation),
    When the user runs `teddy execute`,
    Then the command should fail,
    And the final markdown report should contain a "Failed Action Details" section
    with the current content of the file.
    """
    # Arrange
    file_to_edit = tmp_path / "protected.txt"
    original_content = "This is protected content."
    file_to_edit.write_text(original_content, encoding="utf-8")

    # Make the file read-only to force an execution failure
    import os
    import stat

    os.chmod(file_to_edit, stat.S_IREAD)

    try:
        builder = MarkdownPlanBuilder("Test Plan: Failed Edit")
        builder.add_action(
            "EDIT",
            params={
                "File Path": file_to_edit.name,
                "Description": "Attempt to edit a read-only file.",
            },
            content_blocks={
                "`FIND:`": ("text", "protected content"),
                "`REPLACE:`": ("text", "modified content"),
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
        assert "## Failed Action Details" in result.stdout
        # The report should include the file content for context
        assert original_content in result.stdout
        # Assert the relative path is present as a correct markdown link
        assert (
            f"**Resource:** `[{file_to_edit.name}](/{file_to_edit.name})`"
            in result.stdout
        )

    finally:
        # Cleanup: Restore write permissions so the tmp_path fixture can clean up
        os.chmod(file_to_edit, stat.S_IWRITE | stat.S_IREAD)


def test_report_has_no_extra_newlines_on_successful_validation():
    """
    Given a plan that passes pre-flight validation
    When the plan is executed
    Then the final report must not have a large gap of empty newlines before the ## Execution Summary section.
    """
    # GIVEN a simple valid plan
    plan_builder = MarkdownPlanBuilder("Test Plan: Newline bug")
    plan_builder.add_action(
        "READ", {"Resource": "dummy_file.txt", "Description": "read dummy file"}
    )
    plan_content = plan_builder.build()

    # AND the user will skip the action to get a report quickly without file I/O
    user_input = "n\n\n"

    # WHEN the command is run in an isolated filesystem where the target file exists
    with runner.isolated_filesystem():
        Path("dummy_file.txt").touch()

        result = runner.invoke(
            app,
            ["execute", "--plan-content", plan_content],
            input=user_input,
            catch_exceptions=False,
        )

    # THEN the command should succeed (exit code 0)
    assert result.exit_code == 0, f"CLI invocation failed: {result.stdout}"

    # AND the report should be parsed correctly with a SUCCESS status
    report = parse_markdown_report(result.stdout)
    assert report["run_summary"]["Overall Status"] == "SUCCESS"

    # AND the report should not have excessive newlines before the summary
    # The bug manifests as multiple newlines, potentially with whitespace.
    # We check for a pattern of 3 or more newline/whitespace sequences.
    excessive_newlines_pattern = r"(\s*\n){3,}## Execution Summary"
    assert not re.search(excessive_newlines_pattern, result.stdout), (
        "Found excessive newlines before Execution Summary"
    )
