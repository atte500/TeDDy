from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_create_fails_if_file_exists_without_overwrite(
    tmp_path, monkeypatch, mock_env, mock_user_interactor
):
    # Given a file that already exists
    existing_file = tmp_path / "existing.txt"
    existing_file.write_text("original content", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    # And a plan with a CREATE action targeting that file without Overwrite: true
    plan_content = """# Test Plan
- Status: Green 🟢
- Plan Type: Implementation
- Agent: Developer

## Rationale
```text
### 1. Synthesis
Test scenario.
### 2. Justification
Test scenario.
### 3. Expected Outcome
Test scenario.
### 4. State Dashboard
Test scenario.
```

## Action Plan

### `CREATE`
- File Path: [existing.txt](/existing.txt)
- Description: Try to create an existing file.
```text
new content
```
"""

    # When the plan is executed
    result = runner.invoke(app, ["execute", "--plan-content", plan_content])

    # Then validation must fail
    assert result.exit_code != 0

    # And the failure message must hint at the Overwrite parameter
    assert "File already exists: existing.txt" in result.stdout
    assert "Overwrite: true" in result.stdout
    assert "parameter can be used with caution to bypass this" in result.stdout
