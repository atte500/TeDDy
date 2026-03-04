from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_prune_auto_skipped_in_non_interactive_mode():
    """
    Scenario 1: PRUNE in Non-Interactive Mode
    Given a plan containing a PRUNE action
    When the plan is executed with teddy execute --yes (non-interactive)
    Then the PRUNE action must be automatically marked as SKIPPED
    And the skip reason in the report must be: "Skipped: PRUNE is not supported in non-interactive/manual mode."
    """
    plan_content = """# Prune Plan
- Status: Green 🟢
- Plan Type: Implementation
- Agent: Developer

## Rationale
```text
### 1. Synthesis
Testing PRUNE skip.

### 2. Justification
Required by orchestrator.

### 3. Expected Outcome
Auto-skip.

### 4. State Dashboard
- Goal: Test
```

## Action Plan

### `PRUNE`
- Resource: [dummy.txt](/dummy.txt)
- Description: Remove dummy from context.
"""

    # Run the execute command with --yes
    result = runner.invoke(app, ["execute", "--plan-content", plan_content, "--yes"])

    # Assertions
    assert result.exit_code == 0

    # Check that the PRUNE action is marked as SKIPPED with the correct reason in the output report
    # The CLI output should contain the execution report
    assert "### `PRUNE`: [dummy.txt](/dummy.txt)" in result.stdout
    assert "- **Status:** SKIPPED" in result.stdout
    assert (
        "Skipped: PRUNE is not supported in non-interactive/manual mode."
        in result.stdout
    )


def test_invoke_manual_handoff_in_non_interactive_mode():
    """
    Scenario 2: INVOKE/RETURN in Non-Interactive Mode
    Given a plan containing an INVOKE action
    When the plan is executed with teddy execute --yes (non-interactive)
    Then the executor must treat the action as a PROMPT
    And the output to the user must be a formatted instruction block.
    """
    plan_content = """# Invoke Plan
- Status: Green 🟢
- Plan Type: Implementation
- Agent: Developer

## Rationale
```text
### 1. Synthesis
Testing INVOKE handoff.

### 2. Justification
Required by orchestrator.

### 3. Expected Outcome
Manual handoff block.

### 4. State Dashboard
- Goal: Test
```

## Action Plan

### `INVOKE`
- Agent: Architect
- Handoff Resources:
  - [docs/spec.md](/docs/spec.md)

Handoff to the Architect.
"""

    result = runner.invoke(app, ["execute", "--plan-content", plan_content, "--yes"])

    assert result.exit_code == 0

    # Verify the manual handoff instruction block in stderr (where interactor prints)
    assert "MANUAL HANDOFF REQUIRED:" in result.stderr
    assert "Action: INVOKE" in result.stderr
    assert "Target Agent: Architect" in result.stderr
    assert "Resources: ['docs/spec.md']" in result.stderr
    assert "Message: Handoff to the Architect." in result.stderr

    # Verify the status in the report (stdout)
    assert "### `INVOKE`: [Architect](Architect)" in result.stdout
    assert "- **Status:** COMPLETED" in result.stdout

    # Scenario 3: Report Noise Reduction for Handoffs
    # The message should be in stderr (the manual block) but NOT in the report (stdout)
    assert "Handoff to the Architect." in result.stderr
    assert "Handoff to the Architect." not in result.stdout
