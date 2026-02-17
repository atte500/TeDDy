from pathlib import Path
from typer.testing import CliRunner
from teddy_executor.main import app

runner = CliRunner()


def test_parser_error_generates_report(tmp_path: Path, monkeypatch):
    """
    Given a plan with a syntax error (unexpected text),
    When teddy execute is run,
    Then it should output a valid Execution Report with VALIDATION_FAILED status.
    """
    plan_content = """# Bad Plan
- Status: Green 🟢
- Plan Type: Bugfix
- Agent: Developer

## Rationale
Rationale.

## Action Plan

### `EDIT`
- **File Path:** [test.txt](/test.txt)

Unexpected text here that breaks the parser.

#### `FIND:`
```text
foo
```
#### `REPLACE:`
```text
bar
```
"""
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        # Create a dummy file so EDIT path validation passes (if it got that far)
        (tmp_path / "test.txt").touch()

        result = runner.invoke(
            app, ["execute", "--yes", "--no-copy", "--plan-content", plan_content]
        )

    # Assert that we get a report, not a crash
    # The output should contain the validation error
    # We check for the status. The template might render "Validation Failed" or "VALIDATION_FAILED"
    assert "Validation Failed" in result.stdout or "VALIDATION_FAILED" in result.stdout
    assert "Unexpected content found" in result.stdout
