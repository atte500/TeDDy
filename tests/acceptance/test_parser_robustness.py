from typer.testing import CliRunner

from teddy_executor.__main__ import app

runner = CliRunner()


def test_plan_with_preamble_is_parsed_successfully():
    """
    Scenario 1: A plan with preamble text is parsed and executed successfully.
    """
    plan_content = """This is some preamble text that should be ignored.
It can even have multiple lines.

# Test Plan with Preamble
- Status: Green 🟢
- Plan Type: Test
- Agent: Developer

## Rationale
````text
This is a test rationale.
````

## Action Plan

### `CHAT_WITH_USER`
Hello from the test plan!
"""
    result = runner.invoke(
        app,
        ["execute", "--plan-content", plan_content, "--no-copy"],
        input="y\n",
    )
    assert result.exit_code == 0
    assert "Execution Report" in result.stdout
    assert "Test Plan with Preamble" in result.stdout
    assert "CHAT_WITH_USER" in result.stdout
    assert "SUCCESS" in result.stdout


def test_standard_plan_parses_correctly():
    """
    Scenario 2: A standard plan without preamble parses correctly.
    """
    plan_content = """# Standard Test Plan
- Status: Green 🟢
- Plan Type: Test
- Agent: Developer

## Rationale
````text
This is a test rationale.
````

## Action Plan

### `CHAT_WITH_USER`
Hello from the standard plan!
"""
    result = runner.invoke(
        app,
        ["execute", "--plan-content", plan_content, "--no-copy"],
        input="y\n",
    )
    assert result.exit_code == 0
    assert "Execution Report" in result.stdout
    assert "Standard Test Plan" in result.stdout
    assert "SUCCESS" in result.stdout


def test_plan_without_title_fails_validation():
    """
    Scenario 3: A plan without a title fails validation.
    """
    plan_content = """- Status: Green 🟢
- Plan Type: Test
- Agent: Developer

## Rationale
````text
This is a test rationale.
````

## Action Plan

### `CHAT_WITH_USER`
This should not be executed.
"""
    result = runner.invoke(
        app,
        ["execute", "--plan-content", plan_content, "--no-copy"],
        input="y\n",
    )
    assert result.exit_code == 1
    assert "Plan parsing failed: No Level 1 heading found" in result.stdout
