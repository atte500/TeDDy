from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_execute_allows_chaining_and_directives_in_command_block():
    """
    Scenario: EXECUTE allows chaining and directives in command block
    Given a plan with an EXECUTE action containing a chained command and 'cd'
    When the plan is executed
    Then the validation should pass
    And the command should execute successfully
    """
    plan_content = """# Relaxed Protocol Test
- Status: Green 🟢
- Plan Type: Implementation
- Agent: Developer

## Rationale
```text
### 1. Synthesis
Testing relaxed EXECUTE protocol.
### 2. Justification
Testing chaining and directives.
### 3. Expected Outcome
Success.
### 4. State Dashboard
- Goal: Test
```

## Action Plan

### `EXECUTE`
- Description: Chained command with cd
- Expected Outcome: success.txt is created and listed
```shell
mkdir -p temp_relaxed && cd temp_relaxed && touch success.txt && ls
```
"""
    result = runner.invoke(app, ["execute", "--plan-content", plan_content, "--yes"])

    # This should pass eventually, but will fail now due to validation
    assert result.exit_code == 0
    assert "success.txt" in result.stdout


def test_execute_maintains_statelessness_between_blocks():
    """
    Scenario: EXECUTE maintains statelessness
    Given a plan with two separate EXECUTE blocks
    When the first block changes directory and creates a file
    Then the second block should not see those changes
    """
    plan_content = """# Statelessness Test
- Status: Green 🟢
- Plan Type: Implementation
- Agent: Developer

## Rationale
```text
### 1. Synthesis
Testing statelessness.
### 2. Justification
Testing side effects don't persist.
### 3. Expected Outcome
Failure in second action.
### 4. State Dashboard
- Goal: Test
```

## Action Plan

### `EXECUTE`
- Description: Create dir and file
```shell
mkdir -p temp_stateless && cd temp_stateless && touch inside.txt
```

### `EXECUTE`
- Description: Check for file in root (should not see it)
```shell
ls inside.txt
```
"""
    result = runner.invoke(app, ["execute", "--plan-content", plan_content, "--yes"])

    # Overall execution should fail because the second command fails (ls inside.txt)
    assert result.exit_code == 1
    assert "inside.txt: No such file or directory" in result.stdout
