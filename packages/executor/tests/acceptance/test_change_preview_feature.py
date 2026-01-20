import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from typer.testing import CliRunner

from teddy_executor.core.ports.outbound import IUserInteractor
from teddy_executor.main import app, create_container

runner = CliRunner(mix_stderr=False)


def test_in_terminal_diff_is_shown_for_create_file(tmp_path: Path, monkeypatch):
    """
    Given no external diff tool is configured or found,
    When a `create_file` action is run interactively,
    Then an in-terminal diff should be displayed before the confirmation prompt.
    """
    # GIVEN: A plan to create a new file
    new_file_path = tmp_path / "new_file.txt"
    plan_content = f"""
actions:
  - action: create_file
    path: '{new_file_path}'
    content: |
      First line.
      Second line.
"""
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(plan_content)

    # GIVEN: No diff tool is configured or found
    monkeypatch.setenv("TEDDY_DIFF_TOOL", "")
    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    # WHEN: The plan is executed with interactive approval
    result = runner.invoke(
        app,
        ["execute", str(plan_path)],
        input="y\n",  # Approve the action
    )

    # THEN: The command should succeed and the file should be created
    assert result.exit_code == 0
    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    assert new_file_path.exists()
    assert "Second line" in new_file_path.read_text()

    # AND THEN: A diff should have been printed to stderr
    expected_diff = [
        f"--- a/{new_file_path.name}",
        f"+++ b/{new_file_path.name}",
        "@@ -0,0 +1,2 @@",
        "+First line.",
        "+Second line.",
    ]
    for line in expected_diff:
        assert line in result.stderr

    assert "Approve? (y/n):" in result.stderr


def test_in_terminal_diff_is_shown_as_fallback(tmp_path: Path, monkeypatch):
    """
    Given no external diff tool is configured or found,
    When an `edit` action is run interactively,
    Then an in-terminal diff should be displayed before the confirmation prompt.
    """
    # GIVEN: An initial file and a plan to edit it
    hello_path = tmp_path / "hello.txt"
    hello_path.write_text("Hello, world!")

    plan_content = f"""
actions:
  - action: edit
    path: '{hello_path}'
    find: 'world'
    replace: 'TeDDy'
"""
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(plan_content)

    # GIVEN: No diff tool is configured or found
    monkeypatch.setenv("TEDDY_DIFF_TOOL", "")
    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    # WHEN: The plan is executed with interactive approval
    result = runner.invoke(
        app,
        ["execute", str(plan_path)],
        input="y\n",  # Approve the action
    )

    # THEN: The command should succeed and the file should be changed
    assert result.exit_code == 0
    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    assert hello_path.read_text() == "Hello, TeDDy!"

    # AND THEN: A diff should have been printed to stderr before the prompt
    # We check stderr because prompts are written there.
    expected_diff = [
        "--- a/hello.txt",
        "+++ b/hello.txt",
        "@@ -1 +1 @@",
        "-Hello, world!",
        "+Hello, TeDDy!",
    ]
    for line in expected_diff:
        assert line in result.stderr

    assert "Approve? (y/n):" in result.stderr


def test_vscode_is_used_as_fallback(tmp_path: Path, monkeypatch):
    """
    Given VS Code is available and no custom tool is set,
    When an action is run interactively,
    Then VS Code's diff tool should be invoked.
    """
    # GIVEN: An initial file and a plan to edit it
    hello_path = tmp_path / "hello.txt"
    hello_path.write_text("Hello, world!")

    plan_content = f"""
actions:
  - action: edit
    path: '{hello_path}'
    find: 'world'
    replace: 'TeDDy'
"""
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(plan_content)

    # GIVEN: No custom diff tool is set, but 'code' is available
    monkeypatch.setenv("TEDDY_DIFF_TOOL", "")
    monkeypatch.setattr(
        shutil, "which", lambda cmd: "/usr/bin/code" if cmd == "code" else None
    )

    # WHEN: The plan is executed, mocking subprocess.run
    with patch("subprocess.run") as mock_run:
        result = runner.invoke(
            app,
            ["execute", str(plan_path)],
            input="y\n",
        )

    # THEN: The command should succeed
    assert result.exit_code == 0
    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"

    # AND THEN: subprocess.run should have been called with the correct args
    mock_run.assert_called_once()
    args, _ = mock_run.call_args
    command_list = args[0]
    assert command_list[0] == "/usr/bin/code"
    assert command_list[1] == "--wait"
    assert command_list[2] == "--diff"
    # Ensure the diff is not printed in the terminal as it's handled externally
    assert "--- a/hello.txt" not in result.stderr


def test_custom_diff_tool_is_used_from_env(tmp_path: Path, monkeypatch):
    """
    Given the TEDDY_DIFF_TOOL environment variable is set,
    When an action is run interactively,
    Then the specified custom tool should be invoked.
    """
    # GIVEN: An initial file and a plan to edit it
    hello_path = tmp_path / "hello.txt"
    hello_path.write_text("Hello, world!")

    plan_content = f"""
actions:
  - action: edit
    path: '{hello_path}'
    find: 'world'
    replace: 'TeDDy'
"""
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(plan_content)

    # GIVEN: A custom diff tool is set in the environment
    monkeypatch.setenv("TEDDY_DIFF_TOOL", "meld")
    # Mock shutil.which to ensure 'meld' is "found" and 'code' is not, isolating the test
    monkeypatch.setattr(
        shutil, "which", lambda cmd: f"/usr/bin/{cmd}" if cmd == "meld" else None
    )

    # WHEN: The plan is executed, mocking subprocess.run
    with patch("subprocess.run") as mock_run:
        result = runner.invoke(
            app,
            ["execute", str(plan_path)],
            input="y\n",
        )

    # THEN: The command should succeed
    assert result.exit_code == 0
    report = yaml.safe_load(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"

    # AND THEN: subprocess.run should have been called with the custom tool
    mock_run.assert_called_once()
    args, _ = mock_run.call_args
    command_list = args[0]
    assert command_list[0] == "/usr/bin/meld"
    # Ensure no vscode-specific flags were added
    assert "--wait" not in command_list
    assert "--diff" not in command_list


def test_no_diff_is_shown_for_auto_approved_plans(tmp_path: Path):
    """
    Given any diff tool configuration,
    When a plan is run with the --yes flag,
    Then no diff should be shown and no confirmation prompted.
    """
    # GIVEN: An initial file and a plan to edit it
    hello_path = tmp_path / "hello.txt"
    hello_path.write_text("Hello, world!")

    plan_content = f"""
actions:
  - action: edit
    path: '{hello_path}'
    find: 'world'
    replace: 'TeDDy'
"""
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(plan_content)

    # GIVEN: A mock interactor to spy on
    mock_interactor = MagicMock(spec=IUserInteractor)
    test_container = create_container()
    test_container.register(IUserInteractor, instance=mock_interactor)

    # WHEN: The plan is executed with the --yes flag
    with patch("teddy_executor.main.container", test_container):
        result = runner.invoke(app, ["execute", str(plan_path), "--yes"])

    # THEN: The command should succeed
    assert result.exit_code == 0
    assert hello_path.read_text() == "Hello, TeDDy!"

    # AND THEN: The interactor's confirm_action method should never be called
    mock_interactor.confirm_action.assert_not_called()
    # And no diff should be in the output
    assert "--- Diff ---" not in result.stderr
