from pathlib import Path

from typer.testing import CliRunner

from teddy_executor.__main__ import app
from .helpers import parse_markdown_report
from .plan_builder import MarkdownPlanBuilder

runner = CliRunner()


def test_in_terminal_diff_is_shown_for_create_file(tmp_path: Path, mock_env):
    """
    Given no external diff tool is configured or found,
    When a `create_file` action is run interactively,
    Then an in-terminal diff should be displayed before the confirmation prompt.
    """
    # GIVEN: A plan to create a new file
    new_file_path = tmp_path / "new_file.txt"
    file_content = "First line.\nSecond line.\n"
    builder = MarkdownPlanBuilder("Test Create with Diff")
    builder.add_action(
        "CREATE",
        params={
            "File Path": f"[{new_file_path.name}](/{new_file_path.name})",
            "Description": "Create a file to test diff.",
        },
        content_blocks={"": ("text", file_content)},
    )
    plan_content = builder.build()

    # GIVEN: No diff tool is configured or found
    mock_env.get_env.return_value = ""
    mock_env.which.return_value = None

    # WHEN: The plan is executed with interactive approval
    import os

    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(
            app,
            ["execute", "--no-copy", "--plan-content", plan_content],
            input="y\n",  # Approve the action
        )
    finally:
        os.chdir(original_cwd)

    # THEN: The command should succeed and the file should be created
    assert result.exit_code == 0
    report = parse_markdown_report(result.stdout)
    assert report["run_summary"]["Overall Status"] == "SUCCESS"
    assert new_file_path.exists()
    assert "Second line" in new_file_path.read_text()

    # AND THEN: A New File Preview should have been printed to the merged stderr
    assert "--- New File Preview ---" in result.stderr
    assert f"Path: {new_file_path.name}" in result.stderr
    assert "First line." in result.stderr
    assert "Second line." in result.stderr
    assert "------------------------" in result.stderr

    assert "Approve? (y/n):" in result.stderr


def test_in_terminal_diff_is_shown_as_fallback(tmp_path: Path, mock_env):
    """
    Given no external diff tool is configured or found,
    When an `edit` action is run interactively,
    Then an in-terminal diff should be displayed before the confirmation prompt.
    """
    # GIVEN: An initial file and a plan to edit it
    hello_path = tmp_path / "hello.txt"
    hello_path.write_text("Hello, world!", encoding="utf-8")

    builder = MarkdownPlanBuilder("Test Edit with Diff")
    builder.add_action(
        "EDIT",
        params={
            "File Path": f"[{hello_path.name}](/{hello_path.name})",
            "Description": "Edit to test diff.",
        },
        content_blocks={
            "`FIND:`": ("text", "world"),
            "`REPLACE:`": ("text", "TeDDy"),
        },
    )
    plan_content = builder.build()

    # GIVEN: No diff tool is configured or found
    mock_env.get_env.return_value = ""
    mock_env.which.return_value = None

    # WHEN: The plan is executed with interactive approval
    import os

    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(
            app,
            ["execute", "--no-copy", "--plan-content", plan_content],
            input="y\n",  # Approve the action
        )
    finally:
        os.chdir(original_cwd)

    # THEN: The command should succeed and the file should be changed
    assert result.exit_code == 0
    report = parse_markdown_report(result.stdout)
    assert report["run_summary"]["Overall Status"] == "SUCCESS"
    assert hello_path.read_text() == "Hello, TeDDy!"

    # AND THEN: A diff should have been printed to the merged stdout before the prompt
    expected_diff_output = """--- Diff ---
--- a/hello.txt
+++ b/hello.txt
@@ -1 +1 @@
-Hello, world!
+Hello, TeDDy!
------------"""
    assert expected_diff_output in result.stderr

    assert "Approve? (y/n):" in result.stderr


def test_vscode_is_used_as_fallback(tmp_path: Path, mock_env):
    """
    Given VS Code is available and no custom tool is set,
    When an action is run interactively,
    Then VS Code's diff tool should be invoked.
    """
    # GIVEN: An initial file and a plan to edit it
    hello_path = tmp_path / "hello.txt"
    hello_path.write_text("Hello, world!", encoding="utf-8")

    builder = MarkdownPlanBuilder("Test VSCode Fallback")
    builder.add_action(
        "EDIT",
        params={
            "File Path": f"[{hello_path.name}](/{hello_path.name})",
            "Description": "Edit to test VSCode.",
        },
        content_blocks={
            "`FIND:`": ("text", "world"),
            "`REPLACE:`": ("text", "TeDDy"),
        },
    )
    plan_content = builder.build()

    # GIVEN: No custom diff tool is set, but 'code' is available
    mock_env.get_env.return_value = ""
    mock_env.which.side_effect = lambda cmd: "/usr/bin/code" if cmd == "code" else None
    mock_env.create_temp_file.side_effect = lambda suffix: str(
        tmp_path / f"temp{suffix}"
    )

    # WHEN: The plan is executed
    import os

    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(
            app,
            ["execute", "--no-copy", "--plan-content", plan_content],
            input="y\n",
        )
    finally:
        os.chdir(original_cwd)

    # THEN: The command should succeed
    assert result.exit_code == 0
    report = parse_markdown_report(result.stdout)
    assert report["run_summary"]["Overall Status"] == "SUCCESS"

    # AND THEN: mock_env.run_command should have been called with the correct args
    mock_env.run_command.assert_called_once()
    command_list = mock_env.run_command.call_args[0][0]
    assert command_list[0] == "/usr/bin/code"
    assert command_list[1] == "-r"
    assert command_list[2] == "--diff"
    assert "--wait" not in command_list
    # Ensure the diff is not printed in the terminal as it's handled externally
    assert "--- a/hello.txt" not in result.stdout


def test_custom_diff_tool_is_used_from_env(tmp_path: Path, mock_env):
    """
    Given the TEDDY_DIFF_TOOL environment variable is set with arguments,
    When an action is run interactively,
    Then the specified custom tool should be invoked with its arguments.
    """
    # GIVEN: An initial file and a plan to edit it
    hello_path = tmp_path / "hello.txt"
    hello_path.write_text("Hello, world!", encoding="utf-8")

    builder = MarkdownPlanBuilder("Test Custom Diff Tool")
    builder.add_action(
        "EDIT",
        params={
            "File Path": f"[{hello_path.name}](/{hello_path.name})",
            "Description": "Edit for custom tool.",
        },
        content_blocks={
            "`FIND:`": ("text", "world"),
            "`REPLACE:`": ("text", "TeDDy"),
        },
    )
    plan_content = builder.build()

    # GIVEN: A custom diff tool with arguments is set
    mock_env.get_env.return_value = "nvim -d"
    # Mock which to ensure 'nvim' is "found"
    mock_env.which.side_effect = lambda cmd: "/usr/bin/nvim" if cmd == "nvim" else None
    mock_env.create_temp_file.side_effect = lambda suffix: str(
        tmp_path / f"temp{suffix}"
    )

    # WHEN: The plan is executed
    import os

    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        runner.invoke(
            app,
            ["execute", "--no-copy", "--plan-content", plan_content],
            input="y\n",
        )
    finally:
        os.chdir(original_cwd)

    # THEN: mock_env.run_command should have been called with the parsed command
    mock_env.run_command.assert_called_once()
    command_list = mock_env.run_command.call_args[0][0]
    assert command_list[0] == "/usr/bin/nvim"
    assert command_list[1] == "-d"
    # Ensure no vscode-specific flags were added
    assert "--wait" not in command_list
    assert "--diff" not in command_list


def test_invalid_custom_tool_falls_back_to_terminal(tmp_path: Path, mock_env):
    """
    Given TEDDY_DIFF_TOOL is set to an invalid command,
    And VS Code is available,
    When an action is run,
    Then the system should fall back to the in-terminal diff, not VS Code.
    """
    # GIVEN: A plan to edit a file
    hello_path = tmp_path / "hello.txt"
    hello_path.write_text("Hello!")
    builder = MarkdownPlanBuilder("Test Invalid Tool Fallback")
    builder.add_action(
        "EDIT",
        params={
            "File Path": f"[{hello_path.name}](/{hello_path.name})",
            "Description": "Edit for invalid tool.",
        },
        content_blocks={
            "`FIND:`": ("text", "!"),
            "`REPLACE:`": ("text", ", TeDDy!"),
        },
    )
    plan_content = builder.build()

    # GIVEN: An invalid custom tool is set AND vscode is available
    mock_env.get_env.return_value = "nonexistent-tool"
    mock_env.which.side_effect = lambda cmd: "/usr/bin/code" if cmd == "code" else None

    # WHEN: The plan is executed
    import os

    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(
            app,
            ["execute", "--no-copy", "--plan-content", plan_content],
            input="y\n",
        )
    finally:
        os.chdir(original_cwd)

    # THEN: The command should succeed
    assert result.exit_code == 0

    # AND THEN: The in-terminal diff should be shown
    assert "--- a/hello.txt" in result.stderr
    assert "+Hello, TeDDy!" in result.stderr
    # AND a warning should be printed
    assert (
        "Warning: Custom diff tool 'nonexistent-tool' not found. "
        "Falling back to in-terminal diff." in result.stderr
    )

    # AND THEN: The external tool should NOT have been called
    mock_env.run_command.assert_not_called()


def test_no_diff_is_shown_for_auto_approved_plans(
    tmp_path: Path, monkeypatch, mock_user_interactor
):
    """
    Given any diff tool configuration,
    When a plan is run with the --yes flag,
    Then no diff should be shown and no confirmation prompted.
    """
    # GIVEN: An initial file and a plan to edit it
    hello_path = tmp_path / "hello.txt"
    hello_path.write_text("Hello, world!", encoding="utf-8")
    builder = MarkdownPlanBuilder("Test No Diff on Auto-Approve")
    builder.add_action(
        "EDIT",
        params={
            "File Path": f"[{hello_path.name}](/{hello_path.name})",
            "Description": "Edit for no diff.",
        },
        content_blocks={
            "`FIND:`": ("text", "world"),
            "`REPLACE:`": ("text", "TeDDy"),
        },
    )
    plan_content = builder.build()

    # WHEN: The plan is executed with the --yes flag
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        result = runner.invoke(
            app, ["execute", "--yes", "--no-copy", "--plan-content", plan_content]
        )

    # THEN: The command should succeed
    assert result.exit_code == 0
    assert hello_path.read_text() == "Hello, TeDDy!"

    # AND THEN: The interactor's confirm_action method should never be called
    mock_user_interactor.assert_not_called()
    # And no diff should be in the output
    assert "--- Diff ---" not in result.stdout
