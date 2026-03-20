from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter


def test_edit_content_error_shows_ast(tmp_path, monkeypatch):
    """Ensures that validation errors include the AST summary."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # A plan with invalid content (Missing REPLACE block)
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

    result = adapter.run_command(["execute", "--plan-content", plan_content])

    assert result.exit_code != 0
    assert "Missing REPLACE block" in result.stdout
    assert "Actual Response Structure" in result.stdout
    assert '[000] Heading (Level 1): "Invalid Content Plan"' in result.stdout
