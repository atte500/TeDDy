from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_execute_with_setup_and_allow_failure():
    """
    Scenario: EXECUTE with Setup and Allow Failure
    Given a plan with an EXECUTE action containing:
    - Setup: export FOO=bar && cd src
    - Allow Failure: true
    - A command 'ls'
    And a second EXECUTE action 'echo $FOO'
    When the plan is executed
    Then the first command should be executed with FOO=bar and in src/
    And despite its failure (if ls fails), execution should continue
    """
    plan_content = """# Refactor Test Plan
- Status: Green 🟢
- Plan Type: Implementation
- Agent: Developer

## Rationale
```text
### 1. Synthesis
Testing refactored EXECUTE.
### 2. Justification
Testing Setup and Allow Failure.
### 3. Expected Outcome
Success.
### 4. State Dashboard
- Goal: Test
```

## Action Plan

### `EXECUTE`
- Description: This command will fail but allow failure.
- Setup: cd non_existent_dir_to_force_failure
- Allow Failure: true
- Expected Outcome: Error reported but execution continues.
```shell
ls
```

### `EXECUTE`
- Description: This command should run even though the previous one "failed".
- Expected Outcome: Success.
```shell
echo "I am still running"
```
"""
    # Note: 'cd non_existent_dir_to_force_failure' in Setup should cause a failure
    # if we correctly validate paths in the Setup parameter.

    result = runner.invoke(app, ["execute", "--plan-content", plan_content, "--yes"])

    # Assertions
    # Overall status should be FAILURE because one action failed,
    # but the second action should NOT be SKIPPED.
    assert result.exit_code == 1

    # Check the first action status in report
    assert '### `EXECUTE`: "This command will fail but allow failure."' in result.stdout
    assert "- **Status:** FAILURE" in result.stdout

    # Check that the second action was NOT skipped
    assert (
        '### `EXECUTE`: "This command should run even though the previous one "failed"."'
        in result.stdout
    )
    assert "- **Status:** SUCCESS" in result.stdout
    assert "I am still running" in result.stdout
    assert "Skipped because a previous action failed." not in result.stdout
