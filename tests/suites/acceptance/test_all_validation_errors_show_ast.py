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


def test_unknown_action_error_shows_ast(tmp_path, monkeypatch):
    """Ensures that an unknown action validation error includes the AST summary with a failure marker."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    cli_adapter = CliTestAdapter(monkeypatch, tmp_path)

    # We can't use add_action because it might validate action types.
    # We'll use a raw string for the unknown action.
    plan = """# Plan with unknown action
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
```text
Rationale.
```

## Action Plan
### `NON_EXISTENT_ACTION`
- **Description:** This action does not exist.
"""

    result = cli_adapter.run_command(["execute", "--plan-content", plan])
    assert result.exit_code != 0

    # Assert against the raw stdout, as this is what the harness supports
    assert "Unknown action type: NON_EXISTENT_ACTION" in result.stdout

    # The key assertion: the AST should contain the failure marker
    # We need to check the "Actual Response Structure" section
    assert "[✗]" in result.stdout
