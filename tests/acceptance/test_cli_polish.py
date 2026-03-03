import pytest
from pathlib import Path
from typer.testing import CliRunner
from teddy_executor.__main__ import app
from tests.acceptance.plan_builder import MarkdownPlanBuilder


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def force_terminal_diff(monkeypatch):
    """Ensure that tests always use the in-terminal diff to avoid launching GUI tools."""
    monkeypatch.setenv("TEDDY_DIFF_TOOL", "disabled")


def test_cli_help_is_descriptive_and_accurate(runner):
    """
    Scenario: CLI help is descriptive and accurate
    - Given the teddy CLI
    - When a user runs `teddy --help` or `teddy execute --help`
    - Then the output contains clear descriptions for all commands and options.
    - And the descriptions accurately reflect the project's root-relative path requirements.
    """
    # 1. Test top-level help
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # Ensure commands are listed
    assert "execute" in result.stdout
    assert "context" in result.stdout
    assert "get-prompt" in result.stdout

    # 2. Test execute help specifically for root-relative mentions
    result_execute = runner.invoke(app, ["execute", "--help"])
    assert result_execute.exit_code == 0
    # The requirement is that it mentions "root-relative"
    assert "root-relative" in result_execute.stdout.lower()

    # 3. Test context help for root-relative mentions (it gathers context from root)
    result_context = runner.invoke(app, ["context", "--help"])
    assert result_context.exit_code == 0
    assert "root-relative" in result_context.stdout.lower()


def test_edit_action_shows_unified_diff(runner, tmp_path):
    """
    Scenario: EDIT actions show a unified diff
    - Given a plan with an EDIT action containing multiple FIND/REPLACE pairs
    - When the plan is executed interactively
    - Then the CLI displays exactly one diff for that file.
    - And the diff correctly represents the cumulative result of applying all pairs in sequence.
    """
    # 1. Setup a file to edit
    with runner.isolated_filesystem(temp_dir=tmp_path):
        current_dir = Path.cwd()
        (current_dir / "hello.txt").write_text(
            "line 1\nline 2\nline 3\n", encoding="utf-8"
        )

        # 2. Define a plan with multiple edits for the same file using the builder
        builder = MarkdownPlanBuilder("Test Plan")
        builder.add_action(
            "EDIT",
            params={
                "File Path": "[hello.txt](hello.txt)",
                "Description": "Update multiple lines.",
            },
            content_blocks={
                "FIND:": ("text", "line 1"),
                "REPLACE:": ("text", "LINE ONE"),
                "FIND: ": ("text", "line 3"),
                "REPLACE: ": ("text", "LINE THREE"),
            },
        )
        plan_content = builder.build()

        # 3. Run execute in interactive mode (mocking input 'y' for the action)
        result = runner.invoke(
            app, ["execute", "--plan-content", plan_content], input="y\n"
        )

        # The output should contain the "Unified Diff" indicator and headers.
        assert "--- Diff ---" in result.output
        assert "--- a/hello.txt" in result.output
        assert "+++ b/hello.txt" in result.output

        # Check that it applied BOTH changes in the preview/diff
        assert "-line 1" in result.output
        assert "+LINE ONE" in result.output
        assert "-line 3" in result.output
        assert "+LINE THREE" in result.output

        # CRITICAL: Verify it's a UNIFIED diff (one set of headers)
        assert result.output.count("--- a/hello.txt") == 1

        # Verify file was actually updated correctly
        assert (
            current_dir / "hello.txt"
        ).read_text() == "LINE ONE\nline 2\nLINE THREE\n"

    assert result.exit_code == 0, f"CLI failed with output: {result.output}"


def test_create_action_shows_simple_preview(runner, tmp_path):
    """
    Scenario: CREATE actions show a simple preview
    - Given a plan with a CREATE action
    - When the plan is executed interactively
    - Then the CLI displays a "New File Preview" with the full content of the file.
    """
    # 1. Define a plan with a CREATE action
    # Note: Parser strips trailing newlines from code blocks
    new_content = "This is a brand new file.\nWith multiple lines."

    builder = MarkdownPlanBuilder("Test Plan")
    builder.add_action(
        "CREATE",
        params={
            "File Path": "[new_file.txt](new_file.txt)",
            "Description": "Create a new file.",
        },
        content_blocks={"": ("text", new_content)},
    )
    plan_content = builder.build()

    # 2. Run execute in interactive mode
    with runner.isolated_filesystem(temp_dir=tmp_path):
        current_dir = Path.cwd()
        result = runner.invoke(
            app, ["execute", "--plan-content", plan_content], input="y\n"
        )

        # 4. Verify file was created
        assert (current_dir / "new_file.txt").exists()
        assert (current_dir / "new_file.txt").read_text() == new_content

        assert result.exit_code == 0, f"CLI failed with output: {result.output}"

        # 3. Verify "New File Preview" appears instead of a diff
        assert "--- New File Preview ---" in result.output
        assert "Path: new_file.txt" in result.output
        assert new_content in result.output
        assert "--- Diff ---" not in result.output


def test_create_action_uses_external_editor_for_preview(runner, tmp_path, mock_env):
    """
    Scenario: CREATE actions show a simple preview in the editor if found.
    """
    # 1. Setup Mock System Environment that claims 'code' exists
    mock_env.which.side_effect = lambda cmd: (
        "/usr/local/bin/code" if cmd == "code" else None
    )
    mock_env.get_env.return_value = None
    mock_env.create_temp_file.side_effect = lambda suffix: str(
        tmp_path / f"temp{suffix}"
    )

    # 2. Define a plan with a CREATE action
    new_content = "File content."
    builder = MarkdownPlanBuilder("Test Plan")
    builder.add_action(
        "CREATE",
        params={
            "File Path": "[new_file.txt](new_file.txt)",
            "Description": "Create a new file.",
        },
        content_blocks={"": ("text", new_content)},
    )
    plan_content = builder.build()

    # 3. Run execute
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            app, ["execute", "--plan-content", plan_content], input="y\n"
        )

        # 4. Assertions
        # It should HAVE called the external tool to show the preview
        run_calls = [call[0][0] for call in mock_env.run_command.call_args_list]
        assert any("/usr/local/bin/code" in cmd for cmd in run_calls), (
            f"External editor was NOT called: {run_calls}"
        )

        # But it should NOT have used the --diff flag
        for cmd in run_calls:
            assert "--diff" not in cmd, (
                f"External diff tool was incorrectly called with --diff: {cmd}"
            )

    assert result.exit_code == 0


def test_edit_action_preserves_extension_for_external_diff(runner, tmp_path, mock_env):
    """
    Scenario: External diff previews preserve file extensions for syntax highlighting.
    """
    # 1. Setup Mock System Environment
    mock_env.which.side_effect = lambda cmd: (
        "/usr/local/bin/code" if cmd == "code" else None
    )
    mock_env.get_env.return_value = None

    # Track the suffix used for temp files
    created_suffixes = []

    def mock_create_temp(suffix):
        created_suffixes.append(suffix)
        return str(tmp_path / f"temp{len(created_suffixes)}{suffix}")

    mock_env.create_temp_file.side_effect = mock_create_temp

    # 2. Define a plan with an EDIT action for a .py file
    builder = MarkdownPlanBuilder("Test Plan")
    builder.add_action(
        "EDIT",
        params={
            "File Path": "[script.py](script.py)",
            "Description": "Edit python script.",
        },
        content_blocks={
            "FIND:": ("python", "old_code"),
            "REPLACE:": ("python", "new_code"),
        },
    )
    plan_content = builder.build()

    # 3. Run execute
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Setup the file
        (Path.cwd() / "script.py").write_text("old_code", encoding="utf-8")

        runner.invoke(app, ["execute", "--plan-content", plan_content], input="y\n")

        # 4. Assertions
        # We expect suffixes like ".before.py" and ".after.py"
        assert any(".before.py" in s for s in created_suffixes), (
            f"Expected .before.py in {created_suffixes}"
        )
        assert any(".after.py" in s for s in created_suffixes), (
            f"Expected .after.py in {created_suffixes}"
        )
