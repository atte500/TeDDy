import sys
from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_execute_reports_specific_failing_command_in_multiline_block():
    """
    Scenario: Granular EXECUTE failure reporting
    Given a plan with an EXECUTE block containing multiple commands
    When the second command fails
    Then the action log should explicitly identify the second command as the failure point
    """
    # Using python -c to ensure cross-platform failure behavior for the test logic
    # while the adapter handles the shell wrapping.
    plan_content = f"""# Granular Failure Test
- Status: Green 🟢
- Plan Type: Implementation
- Agent: Developer

## Rationale
```text
### 1. Synthesis
Testing granular failure reporting.
```

## Action Plan

### `EXECUTE`
- Description: Multi-line command where middle fails
```shell
{sys.executable} -c "print('first')"
{sys.executable} -c "import sys; print('second'); sys.exit(1)"
{sys.executable} -c "print('third')"
```
"""
    result = runner.invoke(app, ["execute", "--plan-content", plan_content, "--yes"])

    assert result.exit_code != 0
    # We expect the failure report to contain the failed command in the metadata/details
    # The template renders this as "- **Failed Command:** ..."
    assert "Failed Command" in result.output
    assert "sys.exit(1)" in result.output
