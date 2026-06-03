"""Acceptance tests for EXECUTE fail-fast behavior on interactive prompts."""

from unittest.mock import Mock
from teddy_executor.core.domain.models.shell_output import ShellOutput
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor
from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.observers.report_parser import ReportParser


def test_execute_fails_with_interactive_prompt_message(monkeypatch, tmp_path):
    """
    Scenario: EXECUTE triggers interactive prompt detection → FAILURE.
    Verifies the wiring from ShellAdapter's detection to the CLI's final report.
    """
    # Arrange: Set up the environment with a mocked shell that returns interactive prompt failure
    env = TestEnvironment(monkeypatch, tmp_path).setup()
    mock_shell = Mock(spec=IShellExecutor)
    mock_shell.execute.return_value = ShellOutput(
        return_code=1,
        stdout="FAILURE: Interactive prompt detected",
        stderr="EOFError: EOF when reading a line",
    )
    # Override the default IShellExecutor mock
    env.container.register(IShellExecutor, lambda: mock_shell)

    adapter = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Interactive Prompt Test")
        .add_execute('python -c "input()"', description="Triggers interactive prompt")
        .build()
    )

    # Act
    result = adapter.run_execute_with_plan(plan_content=plan)

    # Assert
    assert result.exit_code == 1, "CLI should exit with failure code"
    report = ReportParser(result.stdout + result.stderr)
    assert report.run_summary["Overall Status"] == "FAILURE"
    log = report.action_logs[0]
    assert log.status == "FAILURE"
    details = log.details
    stdout_text = details.get("stdout", "")
    assert "FAILURE: Interactive prompt detected" in stdout_text
