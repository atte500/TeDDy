from typer.testing import CliRunner
from teddy_executor.__main__ import app
from unittest.mock import MagicMock


def test_enhanced_prompt_marker_in_editor(monkeypatch, tmp_path):
    """
    Scenario 3: Enhanced PROMPT Interactive Flow
    Given a PROMPT action is executed in interactive mode
    When the user selects 'e' to open the editor
    Then the marker instruction in the temporary file must be wrapped in an HTML comment.
    """
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    plan_content = """# Prompt Test
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan
### `PROMPT`
Please provide feedback.
"""

    # We need to intercept the file creation in the editor flow
    from teddy_executor.adapters.outbound.system_environment_adapter import (
        SystemEnvironmentAdapter,
    )

    mock_run = MagicMock()
    monkeypatch.setattr(SystemEnvironmentAdapter, "run_command", mock_run)
    # Prevent deletion so we can read the file
    monkeypatch.setattr(SystemEnvironmentAdapter, "delete_file", MagicMock())
    monkeypatch.setattr(
        SystemEnvironmentAdapter, "which", lambda s, cmd: "/usr/bin/nano"
    )

    # Run command and simulate 'e' then Enter to use editor content
    # First Enter is to press 'e', second Enter is to confirm editor completion
    runner.invoke(app, ["execute", "--plan-content", plan_content], input="e\n\n")

    # Check that run_command was called with a path
    assert mock_run.called
    temp_file_path = mock_run.call_args[0][0][
        -1
    ]  # Last arg of shlex.split(editor) + [path]

    with open(temp_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Requirement: wrapped in HTML comment
    assert "<!--" in content, f"HTML comment start missing in content: {content}"
    assert "-->" in content, "HTML comment end missing"
    assert "Please enter your response above this line" in content


def test_enhanced_prompt_terminal_quick_reply_after_editor_launch(
    monkeypatch, tmp_path
):
    """
    Scenario 3: Enhanced PROMPT Interactive Flow
    And the terminal must continue to allow a single-line reply even while the editor is open.
    """
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    plan_content = """# Prompt Test
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan
### `PROMPT`
Feedback?
"""
    # Mock system environment to prevent actual editor launch blocking
    from teddy_executor.adapters.outbound.system_environment_adapter import (
        SystemEnvironmentAdapter,
    )

    monkeypatch.setattr(SystemEnvironmentAdapter, "run_command", MagicMock())
    monkeypatch.setattr(
        SystemEnvironmentAdapter, "which", lambda s, cmd: "/usr/bin/nano"
    )

    # Input: 'e' to open editor, then "Terminal Reply" to override it
    # The 'e' triggers the editor, and the second line provides the quick reply.
    # We add a trailing newline to ensure the input is processed.
    result = runner.invoke(
        app, ["execute", "--plan-content", plan_content], input="e\nTerminal Reply\n"
    )

    assert result.exit_code == 0
    # Search in details dict as well if report format is concise
    assert (
        "Terminal Reply" in result.stdout
        or "'response': 'Terminal Reply'" in result.stdout
    )


def test_enhanced_prompt_empty_response_confirmation_ux(monkeypatch, tmp_path):
    """
    User Request: Simplify empty response confirmation.
    Given a PROMPT action
    When the user presses Enter without typing anything
    Then the system should prompt to "Press [Enter] again to confirm"
    """
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    plan_content = """# Prompt Test
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Test empty response confirmation.
````

## Action Plan
### `PROMPT`
Empty?
"""

    # Input: Enter (empty), then Enter again (confirm)
    result = runner.invoke(
        app, ["execute", "--plan-content", plan_content], input="\n\n"
    )

    assert result.exit_code == 0
    assert "Press [Enter] again to confirm" in result.stderr
    # The block is omitted when empty to keep the report clean
    assert "User Response" not in result.stdout
