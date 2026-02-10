from pathlib import Path

from .helpers import run_cli_with_markdown_plan_on_clipboard


def test_plan_fails_pre_flight_validation(monkeypatch, tmp_path: Path):
    """
    Given a markdown plan on the clipboard to edit a file with a non-existent FIND block,
    When the user runs `teddy execute`,
    Then the command should fail before executing any actions,
    And the output should be a markdown report detailing the validation failure.
    """
    # Arrange
    file_to_edit = tmp_path / "hello.txt"
    file_to_edit.write_text("Hello, world!")

    # Using as_posix() to ensure cross-platform compatibility for paths in plans
    plan_content = f"""
# Test Plan: Validation Failure
- **Status:** Green 🟢
- **Plan Type:** RED Phase
- **Agent:** Developer

## Rationale
````text
This plan is designed to fail validation because the FIND block doesn't exist.
````

## Action Plan
### `EDIT`
- **File Path:** {file_to_edit.as_posix()}
- **Description:** An edit that should fail validation.

`FIND:`
`````text
Goodbye, world!
`````
`REPLACE:`
`````text
Hello, TeDDy!
`````
"""

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code == 1, (
        f"Expected exit code 1, but got {result.exit_code}. Output:\\n{result.stdout}"
    )
    assert "**Overall Status:** Validation Failed 🔴" in result.stdout
    assert "## Validation Errors" in result.stdout
    assert "The `FIND` block could not be located in the file" in result.stdout
