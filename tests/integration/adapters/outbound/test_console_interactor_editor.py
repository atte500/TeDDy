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

    # Run command and simulate 'e' input for editor
    runner.invoke(app, ["execute", "--plan-content", plan_content], input="e\n")

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


def test_enhanced_prompt_terminal_quick_reply(monkeypatch, tmp_path):
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

    result = runner.invoke(
        app, ["execute", "--plan-content", plan_content], input="Terminal Reply\n"
    )

    assert result.exit_code == 0
    assert "Terminal Reply" in result.stdout
