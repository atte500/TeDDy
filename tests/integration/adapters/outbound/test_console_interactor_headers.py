from typer.testing import CliRunner
from teddy_executor.__main__ import app


def test_prompt_header_uses_agent_name(tmp_path, monkeypatch):
    """
    Scenario 4: Dynamic PROMPT UI Header
    Given a PROMPT action in a plan with Agent: Architect
    When the action is executed
    Then the terminal header should be "--- MESSAGE from Architect ---" in cyan.
    """
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    plan_content = """# Architect Plan
- **Status:** Green 🟢
- **Agent:** Architect

## Rationale
````text
Rationale content.
````

## Action Plan
### `PROMPT`
Hello from Architect.
"""

    result = runner.invoke(
        app, ["execute", "--plan-content", plan_content], input="Got it\n"
    )

    # Check for the expected dynamic header (printed to stderr)
    assert "--- MESSAGE from Architect ---" in result.stderr


def test_prompt_header_defaults_to_teddy(tmp_path, monkeypatch):
    """
    Scenario 4: Dynamic PROMPT UI Header
    Given a PROMPT action in a plan with no agent name
    When the action is executed
    Then the terminal header should be "--- MESSAGE from TeDDy ---".
    """
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    # A plan with a missing Agent field in metadata
    plan_content = """# No Agent Plan
- **Status:** Green 🟢

## Rationale
````text
Rationale.
````

## Action Plan
### `PROMPT`
Hello from TeDDy.
"""

    result = runner.invoke(
        app, ["execute", "--plan-content", plan_content], input="Ok\n"
    )

    assert "--- MESSAGE from TeDDy ---" in result.stderr
