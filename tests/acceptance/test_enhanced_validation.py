from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_structural_validation_error_format():
    """
    Scenario 1: Structural Validation Error
    Given a plan with top-level structural errors (missing ## Rationale)
    When the plan is executed
    Then it should fail with a rich diagnostic report.
    """
    plan_content = """# Plan Missing Rationale
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Pathfinder

## Action Plan
### `READ`
- **Resource:** [README.md](/README.md)
"""

    result = runner.invoke(app, ["execute", "--plan-content", plan_content])

    assert result.exit_code != 0
    output = result.stdout

    # Assertions for the new rich format
    assert '[✓] [000] Heading (Level 1): "Plan Missing Rationale"' in output
    assert '[✓] [001] List: "Status: Green 🟢' in output
    assert (
        "[✗] [002] Heading (Level 2): \"Action Plan\" (Error: Expected a Level 2 Heading containing 'Rationale')"
        in output
    )

    # Verify the general headers are still present or updated appropriately
    assert "--- Actual Document Structure ---" in output
