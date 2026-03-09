import sys
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
    plan_content = f"""# Relaxed Protocol Test
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
{sys.executable} -c "import os; os.makedirs('temp_relaxed', exist_ok=True)" && cd temp_relaxed && {sys.executable} -c "open('success.txt', 'w').close()" && {sys.executable} -c "import os; print('success.txt' if os.path.exists('success.txt') else 'fail')"
```
"""
    result = runner.invoke(app, ["execute", "--plan-content", plan_content, "--yes"])

    assert result.exit_code == 0
    assert "success.txt" in result.output


def test_execute_maintains_statelessness_between_blocks():
    """
    Scenario: EXECUTE maintains statelessness
    Given a plan with two separate EXECUTE blocks
    When the first block changes directory and creates a file
    Then the second block should not see those changes
    """
    plan_content = f"""# Statelessness Test
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
{sys.executable} -c "import os; os.makedirs('temp_stateless', exist_ok=True); open(os.path.join('temp_stateless', 'inside.txt'), 'w').close()"
```

### `EXECUTE`
- Description: Check for file in root (should not see it)
```shell
{sys.executable} -c "import os; import sys; exists = os.path.exists('inside.txt'); print('File found' if exists else 'File not found'); sys.exit(0 if exists else 1)"
```
"""
    result = runner.invoke(app, ["execute", "--plan-content", plan_content, "--yes"])

    # Overall execution should fail because the second command fails
    assert result.exit_code != 0
    assert "File not found" in result.output
