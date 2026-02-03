from typer.testing import CliRunner

from teddy_executor.main import app

runner = CliRunner()


def test_yaml_parsing_with_unquoted_colon():
    """
    Scenario 1: Robust YAML Parsing
    Given a plan.yaml file containing an execute action where the command string
    has a colon but is not quoted.
    When the user executes the plan with teddy.
    Then the plan is parsed and executed successfully without raising a yaml.ScannerError.
    """
    plan_content = """
actions:
  - action: execute
    description: "Run a specific pytest test."
    command: echo hello:world
"""
    result = runner.invoke(
        app,
        ["execute", "--plan-content", plan_content, "-y"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "hello:world" in result.stdout
    assert "status: SUCCESS" in result.stdout
