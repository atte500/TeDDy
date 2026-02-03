from pathlib import Path
from unittest.mock import patch
from typer.testing import CliRunner

from teddy_executor.main import app, create_container
from .helpers import parse_yaml_report


def test_execute_markdown_plan_happy_path(tmp_path: Path):
    """
    Given a valid Markdown plan to create a new file,
    When the user executes the plan,
    Then the file should be created with the correct content and the report is valid.
    """
    # Arrange
    runner = CliRunner()
    file_name = "hello.txt"
    new_file_path = tmp_path / file_name

    plan_content = f"""
# Create a test file
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Developer
- **Goal:** Create a simple file.

## Action Plan

### `CREATE`
- **File Path:** [{str(new_file_path)}]({str(new_file_path)})
- **Description:** Create a hello world file.
````text
Hello, world!
````
"""
    plan_file = tmp_path / "plan.md"
    plan_file.write_text(plan_content, encoding="utf-8")

    real_container = create_container()

    # Act
    with patch("teddy_executor.main.container", real_container):
        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

    # Assert
    assert result.exit_code == 0, (
        f"Teddy failed with stderr: {result.stderr}\\n{result.exception}"
    )
    assert new_file_path.exists(), "The new file was not created."
    assert new_file_path.read_text() == "Hello, world!", (
        "The file content is incorrect."
    )

    # Verify the report output
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"


def test_markdown_edit_action(tmp_path: Path):
    """
    Given a file exists,
    When a Markdown plan with an EDIT action is executed,
    Then the file should be modified correctly.
    """
    # Arrange
    runner = CliRunner()
    file_path = tmp_path / "code.py"
    file_path.write_text("def foo():\n    return 1\n")

    plan_content = f"""
# Edit Plan
- **Status:** Green 🟢

## Action Plan

### `EDIT`
- **File Path:** [{file_path.name}]({str(file_path)})
- **Description:** Change return value.

`FIND:`
````python
def foo():
    return 1
````
`REPLACE:`
````python
def foo():
    return 2
````
"""
    plan_file = tmp_path / "plan.md"
    plan_file.write_text(plan_content, encoding="utf-8")
    real_container = create_container()

    # Act
    with patch("teddy_executor.main.container", real_container):
        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

    # Assert
    assert result.exit_code == 0
    assert "return 2" in file_path.read_text()


def test_markdown_execute_action(tmp_path: Path):
    """
    When a Markdown plan with an EXECUTE action is run,
    Then the command is executed.
    """
    runner = CliRunner()
    plan_content = """
# Exec Plan

## Action Plan

### `EXECUTE`
- **Description:** Echo hello.
- **Expected Outcome:** Hello is printed.
````shell
echo "Hello form Exec"
````
"""
    plan_file = tmp_path / "plan.md"
    plan_file.write_text(plan_content, encoding="utf-8")
    real_container = create_container()

    with patch("teddy_executor.main.container", real_container):
        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

    assert result.exit_code == 0
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    # Depending on shell adapter implementation, output might be in details or stdout
    # Acceptance tests usually verify the report status for execute.


def test_markdown_read_action(tmp_path: Path):
    """
    When a Markdown plan with a READ action is run,
    Then the file content is returned in the report.
    """
    runner = CliRunner()
    target_file = tmp_path / "read_me.txt"
    target_file.write_text("Secret Content")

    plan_content = f"""
# Read Plan

## Action Plan

### `READ`
- **Resource:** [{target_file.name}]({str(target_file)})
- **Description:** Read the secret.
"""
    plan_file = tmp_path / "plan.md"
    plan_file.write_text(plan_content, encoding="utf-8")
    real_container = create_container()

    with patch("teddy_executor.main.container", real_container):
        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

    assert result.exit_code == 0
    report = parse_yaml_report(result.stdout)
    assert report["action_logs"][0]["status"] == "SUCCESS"
    assert report["action_logs"][0]["details"]["content"] == "Secret Content"


def test_markdown_chat_with_user(tmp_path: Path):
    """
    When a Markdown plan with a CHAT_WITH_USER action is run,
    Then the system prompts the user and records the response.
    """
    runner = CliRunner()
    plan_content = """
# Chat Plan

## Action Plan

### `CHAT_WITH_USER`
What is your name?
"""
    plan_file = tmp_path / "plan.md"
    plan_file.write_text(plan_content, encoding="utf-8")
    real_container = create_container()

    with patch("teddy_executor.main.container", real_container):
        # Provide input "y" for confirmation, then "MyName" for the prompt
        result = runner.invoke(app, ["execute", str(plan_file)], input="y\nMyName\n")

    assert result.exit_code == 0
    report = parse_yaml_report(result.stdout)
    assert report["action_logs"][0]["status"] == "SUCCESS"
    assert report["action_logs"][0]["details"]["response"] == "MyName"


def test_markdown_invoke_action(tmp_path: Path):
    """
    When a Markdown plan with an INVOKE action is run,
    Then the system handles it successfully (logging the handoff).
    """
    runner = CliRunner()
    plan_content = """
# Invoke Plan

## Action Plan

### `INVOKE`
- **Agent:** Architect

Please take over.
"""
    plan_file = tmp_path / "plan.md"
    plan_file.write_text(plan_content, encoding="utf-8")
    real_container = create_container()

    with patch("teddy_executor.main.container", real_container):
        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

    assert result.exit_code == 0
    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    assert report["action_logs"][0]["status"] == "SUCCESS"
    # Assuming the default implementation just logs success
