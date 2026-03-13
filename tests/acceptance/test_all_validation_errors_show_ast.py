from typer.testing import CliRunner
from teddy_executor.__main__ import app


def test_edit_content_error_shows_ast(tmp_path, monkeypatch):
    """
    Ensures that an error like "Missing REPLACE block" includes the AST summary.
    """
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    # A plan with a valid top-level structure but invalid action content
    # (Missing REPLACE block)
    plan_content = """# Invalid Content Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan
### `EDIT`
- **File Path:** test.py
- **Description:** Missing replace block.

#### `FIND:`
````python
print("hello")
````
"""

    result = runner.invoke(app, ["execute", "--plan-content", plan_content])

    assert result.exit_code != 0
    # The error message should contain the specific error
    assert "Missing REPLACE block" in result.stdout
    # AND the AST summary
    assert "Actual Document Structure" in result.stdout
    assert '[000] Heading (Level 1): "Invalid Content Plan"' in result.stdout
