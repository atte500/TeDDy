from pathlib import Path
from textwrap import dedent
from .helpers import parse_yaml_report, run_cli_with_markdown_plan_on_clipboard
from .plan_builder import MarkdownPlanBuilder


def test_execute_markdown_plan_happy_path(monkeypatch, tmp_path: Path):
    """
    Given a valid Markdown plan to create a new file,
    When the user executes the plan,
    Then the file should be created with the correct content and the report is valid.
    """
    # Arrange
    file_name = "hello.txt"
    new_file_path = tmp_path / file_name
    file_content = "Hello, world!"

    builder = MarkdownPlanBuilder("Test Create File")
    builder.add_action(
        "CREATE",
        params={
            "File Path": f"[{file_name}](/{file_name})",
            "Description": "Create a hello world file.",
        },
        content_blocks={"": ("text", file_content)},
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code == 0, (
        f"Teddy failed!\nException: {result.exception}\nStdout: {result.stdout}"
    )
    assert new_file_path.exists(), "The new file was not created."
    assert new_file_path.read_text() == file_content, "The file content is incorrect."

    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    assert report["action_logs"][0]["status"] == "SUCCESS"


def test_markdown_edit_action(monkeypatch, tmp_path: Path):
    """
    Given a file exists,
    When a Markdown plan with an EDIT action is executed,
    Then the file should be modified correctly.
    """
    # Arrange
    file_name = "code.py"
    file_to_edit = tmp_path / file_name
    file_to_edit.write_text("def foo():\n    return 1\n")

    find_block = dedent(
        """\
        def foo():
            return 1"""
    )
    replace_block = dedent(
        """\
        def foo():
            return 2"""
    )

    builder = MarkdownPlanBuilder("Test Edit Action")
    builder.add_action(
        "EDIT",
        params={
            "File Path": f"[{file_name}](/{file_name})",
            "Description": "Change return value.",
        },
        content_blocks={
            "`FIND:`": ("python", find_block),
            "`REPLACE:`": ("python", replace_block),
        },
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code == 0, (
        f"Teddy failed with exception: {result.exception}\\n{result.stdout}"
    )
    assert "return 2" in file_to_edit.read_text()


def test_markdown_execute_action(monkeypatch, tmp_path: Path):
    """
    When a Markdown plan with an EXECUTE action is run,
    Then the command is executed.
    """
    builder = MarkdownPlanBuilder("Test Execute Action")
    builder.add_action(
        "EXECUTE",
        params={
            "Description": "Echo hello.",
            "Expected Outcome": "Hello is printed.",
        },
        content_blocks={"COMMAND": ("shell", 'echo "Hello from Exec"')},
    )
    plan_content = builder.build()

    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    assert result.exit_code == 0
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"


def test_markdown_read_action(monkeypatch, tmp_path: Path):
    """
    When a Markdown plan with a READ action is run,
    Then the file content is returned in the report.
    """
    file_name = "read_me.txt"
    target_file = tmp_path / file_name
    target_file.write_text("Secret Content")

    builder = MarkdownPlanBuilder("Test Read Action")
    builder.add_action(
        "READ",
        params={
            "Resource": f"[{file_name}](/{file_name})",
            "Description": "Read the secret.",
        },
    )
    plan_content = builder.build()

    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    assert result.exit_code == 0, (
        f"Teddy failed with exception: {result.exception}\\n{result.stdout}"
    )
    report = parse_yaml_report(result.stdout)
    assert report["action_logs"][0]["status"] == "SUCCESS"
    assert report["action_logs"][0]["details"]["content"] == "Secret Content"


def test_markdown_invoke_action(monkeypatch, tmp_path: Path):
    """
    When a Markdown plan with an INVOKE action is run,
    Then the system handles it successfully (logging the handoff).
    """
    builder = MarkdownPlanBuilder("Test Invoke Action")
    builder.add_action(
        "INVOKE",
        params={"Agent": "Architect", "Handoff Message": "Please take over."},
    )
    plan_content = builder.build()

    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    assert result.exit_code == 0
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    assert report["action_logs"][0]["status"] == "SUCCESS"
