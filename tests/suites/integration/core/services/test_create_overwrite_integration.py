from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_create_passes_if_file_exists_with_overwrite_integration(
    tmp_path, monkeypatch, mock_env, mock_user_interactor
):
    # Given a file that already exists
    existing_file = tmp_path / "existing.txt"
    existing_file.write_text("original content", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    # And a plan with a CREATE action targeting that file WITH Overwrite: true
    plan_content = """# Test Plan
- Status: Green 🟢
- Plan Type: Implementation
- Agent: Developer

## Rationale
```text
### 1. Synthesis
Test.
### 2. Justification
Test.
### 3. Expected Outcome
Test.
### 4. State Dashboard
Test.
```

## Action Plan

### `CREATE`
- File Path: [existing.txt](/existing.txt)
- Overwrite: true
- Description: Overwrite existing file.
```text
new content
```
"""

    # When the plan is executed with --yes (non-interactive)
    result = runner.invoke(app, ["execute", "--yes", "--plan-content", plan_content])

    # Then validation must PASS and execution must succeed
    assert result.exit_code == 0
    assert "**Overall Status:** SUCCESS" in result.stdout
    assert "### `CREATE`" in result.stdout
    assert "**Overwrite:** True" in result.stdout

    # And the file must be overwritten
    assert existing_file.read_text(encoding="utf-8") == "new content"

    # And Scenario 3: The report must include a diff because it's an overwrite
    assert "--- a/existing.txt" in result.stdout
    assert "+++ b/existing.txt" in result.stdout
    assert "-original content" in result.stdout
    assert "+new content" in result.stdout
