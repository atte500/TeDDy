from pathlib import Path

from typer.testing import CliRunner

from teddy_executor.__main__ import app
from .helpers import parse_markdown_report
from .plan_builder import MarkdownPlanBuilder


def test_prompt_action_successful(tmp_path: Path, monkeypatch, container):
    """
    Given a plan containing a 'prompt' action,
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
        "PROMPT",
        params={"prompt": "What is your favorite color?"},
    )
    plan_content = builder.build()

    # Act
    # Refactored to use --plan-content and run from a temp dir
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
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


def test_prompt_action_multiline_editor(tmp_path: Path, monkeypatch, container):
    """
    Given a plan containing a 'prompt' action,
    When the plan is executed and the user chooses to use the external editor ('e'),
    Then the action should succeed and capture the multiline response from the temp file,
    ignoring the instructional comments.
    """
    # Arrange
    runner = CliRunner()
    user_response = "Line 1\nLine 2\n"

    # User types 'e' to open editor, then Enter to confirm completion
    cli_input = "e\n\n"

    builder = MarkdownPlanBuilder("Test Chat Action Multiline")
    builder.add_action(
        "PROMPT",
        params={"prompt": "Write a poem:"},
    )
    plan_content = builder.build()

    # Mock subprocess.run to simulate an editor saving content to the temporary file
    def mock_run_editor(cmd, *args, **kwargs):
        # cmd[0] is the editor, cmd[1] should be the temp file path
        filepath = Path(cmd[1])
        filepath.write_text(
            f"{user_response}\n<!-- Please enter your response above this line. Save and close this file to submit. -->\n"
        )

        # return a mock CompletedProcess
        class MockCompletedProcess:
            returncode = 0

        return MockCompletedProcess()

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        import subprocess

        # Implementation now uses background=True (Popen) for editors
        m.setattr(subprocess, "Popen", mock_run_editor)
        # Also mock run just in case for other parts of the flow
        m.setattr(subprocess, "run", mock_run_editor)
        # Force a specific editor so the fallback logic doesn't try to find 'code' or 'nano'
        m.setenv("EDITOR", "mock_editor")

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


def test_prompt_with_reference_files_flow(tmp_path):
    """
    Scenario: Parser recognizes "Reference Files" in PROMPT and displays them in CLI and Report.
    """
    # Arrange
    runner = CliRunner()
    ref_file = tmp_path / "important_context.md"
    ref_file.write_text("Context content", encoding="utf-8")

    plan_content = f"""
# Test Reference Files
- Status: Green 🟢
- Agent: Developer

## Rationale
````text
Testing reference files standardization.
````

## Action Plan

### `PROMPT`
- **Reference Files:**
  [{ref_file}](/{ref_file})

Please review this context.
"""

    # Act
    # We use --no-interactive to avoid hanging, or we'll need to mock input.
    # For acceptance tests of UI labels, we check the captured output.
    result = runner.invoke(
        app, ["execute", "--plan-content", plan_content], input="\ny\n"
    )

    # Assert
    # If the parser doesn't recognize Reference Files in PROMPT, it might treat it as text.
    # We want it to be recognized as a parameter so it can be formatted specifically.
    assert result.exit_code == 0
    # Check CLI output for the new label
    assert "Reference Files:" in result.stderr
    assert "important_context.md" in result.stderr


def test_invoke_with_reference_files_naming(tmp_path):
    """
    Scenario: Parser recognizes "Reference Files" in INVOKE (replacing Handoff Resources).
    """
    runner = CliRunner()
    ref_file = tmp_path / "handoff_data.json"
    ref_file.write_text("{}", encoding="utf-8")

    plan_content = f"""
# Test Invoke Reference Files
- Status: Green 🟢
- Agent: Developer

## Rationale
````text
Rationale.
````

## Action Plan

### `INVOKE`
- **Agent:** Architect
- **Description:** Moving to design phase.
- **Reference Files:**
  [{ref_file}](/{ref_file})
"""
    # Act
    result = runner.invoke(app, ["execute", "--plan-content", plan_content], input="\n")

    # Assert
    assert result.exit_code == 0
    assert "Reference Files:" in result.stderr
    assert "handoff_data.json" in result.stderr
