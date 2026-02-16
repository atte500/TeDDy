from pathlib import Path

import re
import pytest
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

    # AND the report should be parsed correctly with a SKIPPED status
    report = parse_markdown_report(result.stdout)
    assert report["run_summary"]["Overall Status"] == "SKIPPED"

    # AND the report should not have excessive newlines before the summary
    # The bug manifests as multiple newlines, potentially with whitespace.
    # We check for a pattern of 3 or more newline/whitespace sequences.
    excessive_newlines_pattern = r"(\s*\n){3,}## Execution Summary"
    assert not re.search(excessive_newlines_pattern, result.stdout), (
        "Found excessive newlines before Execution Summary"
    )


def test_failed_execute_action_formats_details_human_readably(
    monkeypatch, tmp_path: Path
):
    """
    Given a plan with an EXECUTE action that fails,
    When the plan is executed,
    Then the final report's "Failed Action Details" section
    should format the stdout, stderr, and return code in a human-readable way.
    """
    # GIVEN a plan with a failing command that produces stdout, stderr, and a non-zero exit code
    failing_command = "python -c \"import sys; print('stdout message'); print('stderr message', file=sys.stderr); sys.exit(42)\""
    plan_builder = MarkdownPlanBuilder("Test Plan: Failing Execute")
    plan_builder.add_action(
        "EXECUTE",
        {
            "Description": "Run a failing command",
            "command": failing_command,
        },
    )
    plan_content = plan_builder.build()

    # WHEN the command is run
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # THEN the command should fail
    assert result.exit_code != 0, "The command should have failed but it succeeded."
    report_text = result.stdout

    # AND the report should contain the failed action details
    assert "## Failed Action Details" in report_text
    assert '### `EXECUTE` on "Run a failing command"' in report_text

    # AND the details should be formatted nicely, not as a raw dict string
    assert "{'stdout':" not in report_text, "Found raw dictionary key for stdout"
    assert "'return_code': 42" not in report_text, (
        "Found raw dictionary key for return_code"
    )

    # AND the key components of the formatted output should be present
    assert "- **Return Code:** `42`" in report_text
    assert "stdout message" in report_text
    assert "stderr message" in report_text


@pytest.mark.xfail(
    reason="This test expects the new, concise report format, which is not yet implemented."
)
def test_successful_plan_execution_report_format(monkeypatch, tmp_path: Path):
    """
    Given a plan that executes successfully,
    When `teddy execute` is run,
    Then the report's `Execution Summary` should appear immediately after the header,
    And each action's `Status` should be on a new, indented line.
    """
    # Arrange
    builder = MarkdownPlanBuilder("Test Plan: Successful Execution")
    builder.add_action(
        "CREATE",
        params={
            "File Path": "new_file.txt",
            "Description": "Create a new file.",
        },
        content_blocks={"`Content:`": ("text", "Hello, TeDDy!")},
    )
    builder.add_action(
        "EXECUTE",
        params={
            "Description": "Simple echo",
            "command": "echo 'Success!'",
            "Expected Outcome": "The command should run successfully.",
        },
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path, user_input="y\ny\n"
    )

    # Assert
    assert result.exit_code == 0, f"CLI invocation failed: {result.stdout}"

    report_lines = [line.strip() for line in result.stdout.strip().split("\n")]

    # Find the start of the summary
    try:
        summary_start_index = report_lines.index("## Execution Summary")
    except ValueError:
        pytest.fail(
            f"The '## Execution Summary' header was not found in the report.\\nReport:\\n{result.stdout}"
        )

    # Assert that the summary comes right after the header block
    # The header block consists of the H1, Overall Status, Start Time, End Time, and a blank line.
    assert summary_start_index <= 5, (
        f"Execution Summary is not positioned correctly after the header. Report:\\n{result.stdout}"
    )

    # Assert status formatting for the CREATE action
    try:
        create_status_index = report_lines.index("- SUCCESS", summary_start_index)
        assert report_lines[create_status_index - 1] == "- Status:", (
            "Status for CREATE is not on a new, indented line."
        )
    except ValueError:
        pytest.fail(
            f"Could not find the expected status format for the CREATE action.\\nReport:\\n{result.stdout}"
        )

    # Assert status formatting for the EXECUTE action
    try:
        execute_status_index = report_lines.index("- SUCCESS", create_status_index + 1)
        assert report_lines[execute_status_index - 1] == "- Status:", (
            "Status for EXECUTE is not on a new, indented line."
        )
    except ValueError:
        pytest.fail(
            f"Could not find the expected status format for the EXECUTE action.\\nReport:\\n{result.stdout}"
        )


def test_markdown_report_for_all_skipped_actions(
    tmp_path: Path,
):
    """
    Scenario: Plan where all actions are skipped reports "Skipped" status
    """
    # GIVEN a valid plan with two actions
    (tmp_path / "hello.txt").write_text("Hello, world!")
    plan_builder = MarkdownPlanBuilder("Test Plan: All Skipped")
    plan_builder.add_action(
        "READ", {"Resource": "hello.txt", "Description": "Read the file"}
    )
    plan_builder.add_action(
        "EXECUTE",
        {"command": "echo 'hello'", "Description": "Run a simple command"},
    )
    plan = plan_builder.build()

    # WHEN the user runs `teddy execute` and skips every action
    with runner.isolated_filesystem(temp_dir=tmp_path) as isolated_path:
        Path(isolated_path, "hello.txt").write_text("Hello, world!")
        result = runner.invoke(
            app,
            ["execute", "--plan-content", plan],
            # Answer "n" to both prompts, with reasons
            input="n\nreason1\nn\nreason2\n",
            catch_exceptions=False,
        )

    # THEN the command should exit with a success code
    assert result.exit_code == 0, f"CLI failed unexpectedly:\n{result.stdout}"

    # AND the final Markdown report's Overall Status must be `SKIPPED`
    # Use regex for a more robust check against markdown formatting
    pattern = r"- \*\*Overall Status:\*\* SKIPPED"
    assert re.search(pattern, result.stdout), (
        f"Pattern '{pattern}' not found in output:\n{result.stdout}"
    )
    assert '#### `READ` on "Read the file"' in result.stdout, (
        "The READ action should be in the log"
    )
    # Check for the new multi-line status format
    expected_status_string = "- **Status:**\n  - SKIPPED"
    # Normalize newlines for cross-platform compatibility
    normalized_stdout = result.stdout.replace("\r\n", "\n")
    assert expected_status_string in normalized_stdout, (
        f"The READ action should be marked as skipped with the new format. Got:\\n{result.stdout}"
    )
    assert '#### `EXECUTE` on "Run a simple command"' in result.stdout, (
        "The EXECUTE action should be in the log"
    )
