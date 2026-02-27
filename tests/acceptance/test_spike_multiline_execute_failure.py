from pathlib import Path

from tests.acceptance.helpers import (
    run_cli_with_markdown_plan_on_clipboard,
    parse_markdown_report,
)
from tests.acceptance.plan_builder import MarkdownPlanBuilder


def test_multiline_execute_failure_is_reported_correctly(monkeypatch, tmp_path: Path):
    """
    Given a multi-line EXECUTE action,
    When an intermediate command fails,
    Then the action status should be FAILED in the report,
    and subsequent commands should not be executed.
    """
    # ARRANGE
    # Create a marker file to check if the last command runs
    marker_file = tmp_path / "marker.txt"

    script_content = f"""
echo "This command will succeed."
ls /non-existent-directory-to-force-failure
echo "This command should not run" > {marker_file}
""".strip()

    builder = MarkdownPlanBuilder("Test Multi-line EXECUTE Failure")
    builder.add_action(
        "EXECUTE",
        params={
            "Description": "A test script designed to fail.",
            "Expected Outcome": "The action fails and is reported correctly.",
        },
        content_blocks={"COMMAND": ("shell", script_content)},
    )
    plan_content = builder.build()

    # ACT
    # We expect a non-zero exit code, so we don't check it here.
    # The primary assertion is on the report content.
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # ASSERT
    assert not marker_file.exists(), (
        "The command after the failing one should not have been executed."
    )

    report = parse_markdown_report(result.stdout)

    # Assert on the Run Summary
    assert report["run_summary"]["Overall Status"] == "FAILURE", (
        "The plan execution status should be FAILURE if an action fails."
    )

    # Assert on the specific Action Log
    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"
    # Note: Summary parsing is limited in the current helper,
    # but we can check the details if needed.
