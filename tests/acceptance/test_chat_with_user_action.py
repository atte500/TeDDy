from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from teddy_executor.__main__ import app, create_container
from .helpers import parse_markdown_report
from .plan_builder import MarkdownPlanBuilder


def test_chat_with_user_action_successful(tmp_path: Path, monkeypatch):
    """
    Given a plan containing a 'chat_with_user' action,
    When the plan is executed and the user provides input,
    Then the action should succeed and capture the response.
    """
    # Arrange
    runner = CliRunner()
    user_response = "Blue"
    # User input is the response, followed by an empty line to terminate.
    cli_input = f"{user_response}\n\n"

    builder = MarkdownPlanBuilder("Test Chat Action")
    # Refactored to use MarkdownPlanBuilder instead of yaml.dump
    builder.add_action(
        "CHAT_WITH_USER",
        params={"prompt": "What is your favorite color?"},
    )
    plan_content = builder.build()

    real_container = create_container()

    # Act
    # Refactored to use --plan-content and run from a temp dir
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        with patch("teddy_executor.__main__.container", real_container):
            result = runner.invoke(
                app,
                ["execute", "--yes", "--no-copy", "--plan-content", plan_content],
                input=cli_input,
            )

    # Assert
    assert result.exit_code == 0, f"CLI failed: {result.stdout}"

    report = parse_markdown_report(result.stdout)
    assert report["run_summary"]["Overall Status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"

    details_dict = action_log["details"]
    assert details_dict["response"] == user_response


def test_chat_with_user_action_multiline_editor(tmp_path: Path, monkeypatch):
    """
    Given a plan containing a 'chat_with_user' action,
    When the plan is executed and the user chooses to use the external editor ('e'),
    Then the action should succeed and capture the multiline response from the temp file,
    ignoring the instructional comments.
    """
    # Arrange
    runner = CliRunner()
    user_response = "Line 1\nLine 2\n"

    # User types 'e' to open editor
    cli_input = "e\n"

    builder = MarkdownPlanBuilder("Test Chat Action Multiline")
    builder.add_action(
        "CHAT_WITH_USER",
        params={"prompt": "Write a poem:"},
    )
    plan_content = builder.build()
    real_container = create_container()

    # Mock subprocess.run to simulate an editor saving content to the temporary file
    def mock_run_editor(cmd, *args, **kwargs):
        # cmd[0] is the editor, cmd[1] should be the temp file path
        filepath = Path(cmd[1])
        filepath.write_text(
            f"{user_response}\n--- Please enter your response above this line. Save and close this file to submit. ---\n"
        )

        # return a mock CompletedProcess
        class MockCompletedProcess:
            returncode = 0

        return MockCompletedProcess()

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        import subprocess

        m.setattr(subprocess, "run", mock_run_editor)
        # Force a specific editor so the fallback logic doesn't try to find 'code' or 'nano'
        m.setenv("EDITOR", "mock_editor")

        with patch("teddy_executor.__main__.container", real_container):
            result = runner.invoke(
                app,
                ["execute", "--yes", "--no-copy", "--plan-content", plan_content],
                input=cli_input,
            )

    # Assert
    assert result.exit_code == 0, f"CLI failed: {result.stdout}"

    report = parse_markdown_report(result.stdout)
    assert report["run_summary"]["Overall Status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"

    details_dict = action_log["details"]
    # The response should be exactly what we wrote above the comment line
    assert details_dict["response"] == user_response.strip()
