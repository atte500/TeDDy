from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_prune_auto_skipped_in_non_interactive_mode():
    """
    Scenario 1: PRUNE in Non-Interactive Mode
    Given a plan containing a PRUNE action
    When the plan is executed with teddy execute --yes (non-interactive)
    Then the PRUNE action must be automatically marked as SKIPPED
    And the skip reason in the report must be: "Skipped: PRUNE is not supported in manual execution mode."
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
    assert "Skipped: PRUNE is not supported in manual execution mode." in result.stdout


def test_invoke_interactive_approval():
    """Scenario 2 (Interactive): INVOKE with interactive approval should succeed."""
    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Developer

## Rationale
```text
Rationale
```

## Action Plan
### `INVOKE`
- **Agent:** Architect
- **Description:** Handoff to the Architect.
- **Handoff Resources:**
[docs/spec.md](/docs/spec.md)
"""
    # Test interactive mode: user approves by pressing Enter
    result = runner.invoke(app, ["execute", "--plan-content", plan_content], input="\n")

    assert result.exit_code == 0, f"CLI exited with error:\n{result.stdout}"

    # Verify the manual handoff instruction block in stderr (where interactor prints)
    assert "HANDOFF REQUEST: INVOKE" in result.stderr
    assert "Target Agent: Architect" in result.stderr
    assert "docs/spec.md" in result.stderr
    assert "Handoff to the Architect." in result.stderr

    # Verify the status in the report (stdout)
    assert "### `INVOKE`: Architect" in result.stdout
    assert "- **Status:** SUCCESS" in result.stdout
    assert "- **Description:** Handoff to the Architect." in result.stdout

    # Handoff resources should be links, not in a code block
    assert "[docs/spec.md](/docs/spec.md)" in result.stdout


def test_invoke_non_interactive_must_interrupt():
    """Scenario 2 (--yes): INVOKE with --yes flag should still interrupt and prompt."""
    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Developer

## Rationale
```text
Rationale
```

## Action Plan
### `INVOKE`
- **Agent:** Architect
- **Description:** Handoff to the Architect.
- **Handoff Resources:**
[docs/spec.md](/docs/spec.md)
"""
    # Even with --yes, it should prompt for input. Providing Enter to approve.
    result_yes = runner.invoke(
        app, ["execute", "--plan-content", plan_content, "--yes"], input="\n"
    )
    assert result_yes.exit_code == 0, f"CLI exited with error:\n{result_yes.stdout}"
    assert "- **Status:** SUCCESS" in result_yes.stdout
    # INTERRUPT CHECK: It must show the prompt even with --yes
    assert "HANDOFF REQUEST: INVOKE" in result_yes.stderr


def test_invoke_rejected_in_non_interactive_mode():
    """
    Scenario 2 (Rejection): INVOKE/RETURN in Non-Interactive Mode
    Given a plan containing an INVOKE action
    When the plan is executed
    And the user rejects the handoff with a reason
    Then the action status in the final report must be FAILURE
    And the rejection reason must be in the report.
    """
    plan_content = """# Invoke Plan
- Status: Green 🟢
- Plan Type: Implementation
- Agent: Developer

## Rationale
```text
### 1. Synthesis
Testing INVOKE rejection.
### 2. Justification
Required by orchestrator.
### 3. Expected Outcome
Handoff rejection.
### 4. State Dashboard
- Goal: Test
```

## Action Plan

### `INVOKE`
- Agent: Architect
- Description: Handoff to the Architect.
- Handoff Resources:
[docs/spec.md](/docs/spec.md)
"""

    rejection_reason = "Not ready for architect yet."
    result = runner.invoke(
        app, ["execute", "--plan-content", plan_content], input=rejection_reason + "\n"
    )

    # It should fail overall because an action failed
    assert result.exit_code == 1

    # Verify the status in the report (stdout)
    assert "### `INVOKE`: Architect" in result.stdout
    assert "- **Status:** FAILURE" in result.stdout
    assert "- **Description:** Handoff to the Architect." in result.stdout
    assert f"Manual handoff rejected by user: {rejection_reason}" in result.stdout
