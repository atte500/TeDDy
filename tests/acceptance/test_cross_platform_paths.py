import pytest
from pathlib import Path
from tests.acceptance.helpers import (
    run_cli_with_markdown_plan_on_clipboard,
    parse_markdown_report,
)


def test_execute_plan_with_windows_style_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """
    Acceptance Criteria: Executing a plan with Windows-style paths
    - Given a file named "target_dir/pyproject.toml" exists with the content "Hello".
    - And a plan is created for an `EDIT` action with the file path specified using backslashes.
    - When the user executes the plan.
    - Then the plan should execute successfully.
    """
    # 1. Setup: Create a temporary file in a subdirectory
    target_dir = tmp_path / "target_dir"
    target_dir.mkdir()
    target_file = target_dir / "pyproject.toml"
    target_file.write_text("Hello\n", encoding="utf-8")

    # 2. Construct the Plan using Windows-style paths (\)
    windows_path = "target_dir\\pyproject.toml"

    plan_content = f"""
# Test Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan

### `EDIT`
- **File Path:** [{windows_path}](/{windows_path})
- **Description:** Edit a file using a Windows-style path.

#### `FIND:`
```text
Hello
```
#### `REPLACE:`
```text
World
```
"""

    # 3. Execute
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # 4. Assertions
    assert result.exit_code == 0
    report = parse_markdown_report(result.stdout)

    assert "Overall Status" in report["run_summary"]
    assert report["run_summary"]["Overall Status"] == "SUCCESS"

    # Verify the file was actually edited
    assert target_file.read_text(encoding="utf-8") == "World\n"
