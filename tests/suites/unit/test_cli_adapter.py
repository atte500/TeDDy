from unittest.mock import patch
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


def test_execute_plan_returns_parsed_report(env):
    """
    Verifies that CliTestAdapter can execute a plan and return a ReportParser.
    """
    # Arrange
    # We need a mock for the RunPlanUseCase because CliTestAdapter drives the real CLI
    # which resolves the use case from the container.
    # For this unit test, we will verify the adapter correctly calls the CLI.

    builder = MarkdownPlanBuilder("Test Plan")
    builder.add_create("hello.txt", "world")
    plan_content = builder.build()

    adapter = CliTestAdapter(env._monkeypatch, env.workspace)

    # Act
    # We use a real CLI invocation but we expect it to fail or be mocked
    # depending on how we implement the adapter.
    # For the RED state, we just want to prove the method exists and returns a parser.
    report = adapter.execute_plan(plan_content)

    # Assert
    from tests.harness.observers.report_parser import ReportParser

    assert isinstance(report, ReportParser)
    assert "Overall Status" in report.summary


def test_run_command_direct(env):
    """Verifies the adapter can run arbitrary CLI commands."""
    adapter = CliTestAdapter(env._monkeypatch, env.workspace)

    # We mock find_prompt_content to avoid needing real prompt files on disk
    with patch(
        "teddy_executor.prompts.find_prompt_content",
        return_value="Mock Pathfinder Prompt",
    ):
        result = adapter.run_command(["get-prompt", "pathfinder"])
        assert result.exit_code == 0
        assert "Mock Pathfinder Prompt" in result.stdout
