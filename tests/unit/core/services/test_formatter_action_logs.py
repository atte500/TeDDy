from datetime import datetime, timezone

from teddy_executor.core.domain.models import WebSearchResults
from teddy_executor.core.domain.models.execution_report import (
    ActionLog,
    ActionStatus,
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.services.markdown_report_formatter import (
    MarkdownReportFormatter,
)


def test_formats_read_action_with_resource_contents():
    """
    Given an ExecutionReport with a successful READ action,
    When the report is formatted,
    Then the output should include a 'Resource Contents' section with the file content.
    """
    # Arrange
    formatter = MarkdownReportFormatter()
    file_content = "Hello from the file!"
    report = ExecutionReport(
        plan_title="Test Plan",
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        action_logs=[
            ActionLog(
                action_type="read",
                status=ActionStatus.SUCCESS,
                params={"Resource": "test.txt"},
                details={"content": file_content},
            )
        ],
    )

    # Act
    formatted_report = formatter.format(report)

    # Assert
    assert "## Resource Contents" in formatted_report
    assert file_content in formatted_report
    # New format: H3 header with link
    assert "### [test.txt](/test.txt)" in formatted_report


def test_formats_failed_edit_action_with_file_content():
    """
    Given an ExecutionReport for a failed EDIT action,
    When the report is formatted according to the new spec,
    Then it should not contain a 'Failed Action Details' section,
    And it should contain a 'Resource Contents' section.
    """
    # Arrange
    formatter = MarkdownReportFormatter()
    file_content = "Original content of the file."
    error_message = "Permission denied."
    report = ExecutionReport(
        plan_title="Test Plan",
        run_summary=RunSummary(
            status=RunStatus.FAILURE,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        action_logs=[
            ActionLog(
                action_type="edit",
                status=ActionStatus.FAILURE,
                params={"path": "config.txt"},
                details={"error": error_message, "content": file_content},
            )
        ],
    )

    # Act
    formatted_report = formatter.format(report)

    # Assert
    assert "## Failed Action Details" not in formatted_report
    assert "## Action Log" in formatted_report

    # Check for the inline status format for FAILURE
    expected_status_string = "- **Status:** FAILURE"
    normalized_report = formatted_report.replace("\r\n", "\n")
    assert expected_status_string in normalized_report

    assert "## Resource Contents" in formatted_report
    assert file_content in formatted_report


def test_formats_action_status_inline():
    """
    Given an ExecutionReport with a successful action,
    When the report is formatted,
    Then the action's status should be on the same line as the label.
    """
    # Arrange
    formatter = MarkdownReportFormatter()
    report = ExecutionReport(
        plan_title="Test Plan",
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        action_logs=[
            ActionLog(
                action_type="CREATE",
                status=ActionStatus.SUCCESS,
                params={"path": "new_file.txt"},
            )
        ],
    )

    # Act
    formatted_report = formatter.format(report)

    # Assert
    assert "- **Status:** SUCCESS" in formatted_report


def test_formats_multiline_execute_command_correctly():
    """
    Given an EXECUTE action with a multi-line command,
    When formatted,
    Then the code block should have correct newlines for fences.
    """
    formatter = MarkdownReportFormatter()
    report = ExecutionReport(
        plan_title="Test",
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        action_logs=[
            ActionLog(
                action_type="EXECUTE",
                status=ActionStatus.SUCCESS,
                params={
                    "command": "git add .\ngit commit",
                    "expected_outcome": "Commit succeeds",
                },
            )
        ],
    )

    output = formatter.format(report)

    # We expect:
    # - **Expected outcome:** Commit succeeds
    #
    # - **Command:**
    # ```shell
    # git add .
    # git commit
    # ```

    # Ensure expected outcome is first
    assert "- **Expected outcome:** Commit succeeds" in output

    # Ensure command follows with correct spacing and language
    # The template renders:
    # - **Command:**
    # ```shell
    assert "- **Command:**\n```shell\ngit add .\ngit commit\n```" in output


def test_formats_return_action_correctly():
    """
    Given a RETURN action with resources and description,
    When formatted,
    Then resources should be links and description should be in the body.
    """
    formatter = MarkdownReportFormatter()
    report = ExecutionReport(
        plan_title="Test",
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        action_logs=[
            ActionLog(
                action_type="RETURN",
                status=ActionStatus.SUCCESS,
                params={
                    "handoff_resources": ["docs/A.md", "docs/B.md"],
                    "description": "Task complete.",
                },
            )
        ],
    )

    output = formatter.format(report)

    # Check Reference Files formatting (Example B: multi-line links)
    assert "[docs/A.md](/docs/A.md)" in output
    assert "[docs/B.md](/docs/B.md)" in output

    # Check formatting
    # The header should be just the action type
    assert "### `RETURN`" in output
    # The description should be in the body
    assert "- **Description:** Task complete." in output
    # Ensure 'Message' is not present
    assert "- **Message:**" not in output


def test_formats_failed_execute_action_details_human_readably():
    """
    Given an ExecutionReport with a failed EXECUTE action,
    When the report is formatted,
    Then the output should format the details in a human-readable way.
    """
    # Arrange
    formatter = MarkdownReportFormatter()
    details = {
        "stdout": "stdout message",
        "stderr": "stderr message",
        "return_code": 42,
    }
    report = ExecutionReport(
        plan_title="Test Plan",
        run_summary=RunSummary(
            status=RunStatus.FAILURE,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        action_logs=[
            ActionLog(
                action_type="execute",
                status=ActionStatus.FAILURE,
                params={"command": "a bad command"},
                details=details,
            )
        ],
    )

    # Act
    formatted_report = formatter.format(report)

    # Assert
    # Raw dictionary string should NOT be present
    assert "{'stdout':" not in formatted_report
    assert "'return_code': 42" not in formatted_report

    # Human-readable format SHOULD be present
    assert "- **Return Code:** `42`" in formatted_report
    assert "#### `stdout`" in formatted_report
    assert "```text\nstdout message\n```" in formatted_report
    assert "#### `stderr`" in formatted_report
    assert "```text\nstderr message\n```" in formatted_report


def test_formats_research_action_with_websearchresults():
    """
    Given an ExecutionReport with a RESEARCH action log containing a WebSearchResults dict,
    When the report is formatted,
    Then it should correctly render the results from the dictionary.
    """
    # Arrange
    formatter = MarkdownReportFormatter()
    web_search_results: WebSearchResults = {
        "query_results": [
            {
                "query": "python typeddict",
                "results": [
                    {
                        "title": "Python Docs - TypedDict",
                        "href": "https://docs.python.org/3/library/typing.html#typing.TypedDict",
                        "body": "Official documentation for TypedDict.",
                    }
                ],
            }
        ]
    }
    report = ExecutionReport(
        plan_title="Test Plan",
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        action_logs=[
            ActionLog(
                action_type="RESEARCH",
                status=ActionStatus.SUCCESS,
                params={"Description": "Research TypedDicts"},
                details=web_search_results,
            )
        ],
    )

    # Act
    formatted_report = formatter.format(report)

    # Assert
    assert "**Query:** `python typeddict`" in formatted_report
    assert (
        "[Python Docs - TypedDict](https://docs.python.org/3/library/typing.html#typing.TypedDict)"
        in formatted_report
    )
    assert "Official documentation for TypedDict." in formatted_report


def test_formats_validation_failed_report_with_errors():
    """
    Given an ExecutionReport with a VALIDATION_FAILED status and error messages,
    When the report is formatted,
    Then the output should include a 'Validation Errors' section with the messages.
    """
    # Arrange
    formatter = MarkdownReportFormatter()
    error_messages = [
        "EXECUTE action must contain exactly one command.",
        "Command chaining with '&&' is not allowed.",
    ]
    report = ExecutionReport(
        plan_title="Invalid Plan",
        run_summary=RunSummary(
            status=RunStatus.VALIDATION_FAILED,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        validation_result=error_messages,
    )

    # Act
    formatted_report = formatter.format(report)

    # Assert
    assert "## Validation Errors" in formatted_report
    assert "EXECUTE action must contain exactly one command." in formatted_report
    assert "---" in formatted_report
    assert "Command chaining with '&&' is not allowed." in formatted_report


def test_formats_prompt_action_omits_prompt_text():
    """
    Given a PROMPT action,
    When the report is formatted,
    Then the AI prompt content should be omitted, showing only the interaction.
    """
    formatter = MarkdownReportFormatter()
    report = ExecutionReport(
        plan_title="Test",
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        action_logs=[
            ActionLog(
                action_type="PROMPT",
                status=ActionStatus.SUCCESS,
                params={"prompt": "AI question here?"},
                details={"user_input": "User answer here."},
            )
        ],
    )

    output = formatter.format(report)

    assert "User answer here." in output
    assert "AI question here?" not in output


def test_formats_invoke_action_omits_details_block():
    """
    Given an INVOKE action,
    When the report is formatted,
    Then it should omit the 'Details' section to keep the handoff clean,
    And Agent should be in the header.
    """
    formatter = MarkdownReportFormatter()
    report = ExecutionReport(
        plan_title="Test",
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        action_logs=[
            ActionLog(
                action_type="INVOKE",
                status=ActionStatus.SUCCESS,
                params={
                    "Agent": "Architect",
                    "description": "Handoff to architect.",
                    "message": "Take over.",
                },
            )
        ],
    )

    output = formatter.format(report)

    assert "### `INVOKE`: Architect" in output
    assert "- **Description:** Handoff to architect." in output
    assert "- **Details:**" not in output


def test_formats_handoff_includes_details_when_skipped():
    """
    Given an INVOKE action that is SKIPPED,
    When formatted,
    Then the report SHOULD include the 'Details' section (e.g., for auto-skip reasons).
    """
    formatter = MarkdownReportFormatter()
    report = ExecutionReport(
        plan_title="Test",
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        action_logs=[
            ActionLog(
                action_type="INVOKE",
                status=ActionStatus.SKIPPED,
                params={"Agent": "Architect", "message": "Ignored."},
                details="Skipped because a previous action failed.",
            )
        ],
    )

    output = formatter.format(report)

    assert "- **Status:** SKIPPED" in output
    assert "- **Details:** `Skipped because a previous action failed.`" in output
