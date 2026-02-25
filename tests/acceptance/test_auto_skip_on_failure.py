from typer.testing import CliRunner
from teddy_executor.main import app

runner = CliRunner()


def test_auto_skip_on_execution_failure():
    """
    Scenario: An EXECUTE action fails mid-plan
    Given a plan containing two EXECUTE actions.
    And the first EXECUTE action is a command that will fail.
    And the second EXECUTE action is a valid command.
    When the user executes the plan.
    Then the execution report's "Overall Status" should be FAILURE.
    And the report should show the first action as FAILURE.
    And the report should show the second action as SKIPPED with the correct reason.
    """
    plan_content = """# Auto-Skip Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan
### `EXECUTE`
- **Description:** This command will fail
- **Expected Outcome:** The command exits with code 1
````shell
exit 1
````

### `EXECUTE`
- **Description:** This command should be skipped
- **Expected Outcome:** It does not run
````shell
echo "THIS_SHOULD_NOT_BE_EXECUTED"
````
"""
    result = runner.invoke(app, ["execute", "--plan-content", plan_content, "-y"])

    # Assert overall status is Failure
    assert "- **Overall Status:** FAILURE" in result.stdout, (
        "Overall status should be Failed"
    )

    # Assert the skip reason is present in the report for the second action
    assert "Skipped because a previous action failed." in result.stdout, (
        "Should contain the system skip reason"
    )
