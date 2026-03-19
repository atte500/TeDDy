from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


def test_prompt_header_uses_agent_name(tmp_path, monkeypatch):
    """
    Scenario 4: Dynamic PROMPT UI Header
    Given a PROMPT action in a plan with Agent: Architect
    When the action is executed
    Then the terminal header should be "--- MESSAGE from Architect ---" in cyan.
    """
    TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    cli = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Architect Plan")
        .with_agent("Architect")
        .add_prompt("Hello from Architect.")
        .build()
    )

    result = cli.run_execute_with_plan(plan, input="Got it\n", interactive=True)

    # Check for the expected dynamic header (printed to stderr)
    assert "--- MESSAGE from Architect ---" in result.stderr


def test_prompt_header_defaults_to_teddy(tmp_path, monkeypatch):
    """
    Scenario 4: Dynamic PROMPT UI Header
    Given a PROMPT action in a plan with no agent name
    When the action is executed
    Then the terminal header should be "--- MESSAGE from TeDDy ---".
    """
    TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    cli = CliTestAdapter(monkeypatch, tmp_path)

    # A plan with no agent name
    plan = (
        MarkdownPlanBuilder("No Agent Plan")
        .with_agent(None)
        .add_prompt("Hello from TeDDy.")
        .build()
    )

    result = cli.run_execute_with_plan(plan, input="Ok\n", interactive=True)

    assert "--- MESSAGE from TeDDy ---" in result.stderr
