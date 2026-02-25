from pathlib import Path
from .helpers import run_cli_with_markdown_plan_on_clipboard


def test_edit_action_reports_all_find_block_failures(monkeypatch, tmp_path: Path):
    """
    Scenario 1: An `EDIT` action with multiple invalid `FIND` blocks is validated.
    """
    # Arrange
    target_file = tmp_path / "target.txt"
    target_file.write_text("This is the original content.", encoding="utf-8")

    plan_content = f"""# Comprehensive Validation Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan

### `EDIT`
- **File Path:** [{target_file.name}](/{target_file.name})
- **Description:** Edit with multiple bad finds

#### `FIND:`
```text
NonExistentText1
```
#### `REPLACE:`
```text
Replacement1
```

#### `FIND:`
```text
NonExistentText2
```
#### `REPLACE:`
```text
Replacement2
```
"""

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code != 0, "CLI should fail due to validation errors."

    # Assert that BOTH errors are reported in the output
    assert "NonExistentText1" in result.output, "First FIND block error missing."
    assert "NonExistentText2" in result.output, (
        "Second FIND block error missing. Validator likely short-circuited."
    )


def test_edit_action_with_no_match_provides_diff(monkeypatch, tmp_path: Path):
    """
    Scenario 2: An `EDIT` action with a mismatched `FIND` block is validated, providing a diff.
    """
    # Arrange
    target_file = tmp_path / "target.txt"
    target_file.write_text("This is the original content", encoding="utf-8")

    plan_content = f"""# Diff Feedback Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan

### `EDIT`
- **File Path:** [{target_file.name}](/{target_file.name})
- **Description:** Edit with a typo

#### `FIND:`
```text
This is the orignal content
```
#### `REPLACE:`
```text
This is the new content
```
"""

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code != 0, "CLI should fail due to validation error."

    # The diff should highlight the missing 'i' in "original"
    assert "- This is the orignal content" in result.output
    assert "+ This is the original content" in result.output
    assert "?" in result.output
    assert (
        "+" in result.output.split("?")[1].split("\n")[0]
    )  # Check that a '+' is in the intraline diff line
