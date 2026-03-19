from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


def test_cli_help_output(monkeypatch, tmp_path):
    """Verify the help output is available."""
    TestEnvironment(monkeypatch, tmp_path).setup()
    cli = CliTestAdapter(monkeypatch, cwd=tmp_path)
    result = cli.run_cli_command(["--help"])
    assert result.exit_code == 0
    assert "Usage: " in result.stdout


def test_cli_colorized_status_output(tmp_path, monkeypatch):
    """
    Scenario: Verify status output in CLI.
    """
    TestEnvironment(monkeypatch, tmp_path).setup()
    cli = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Color Test")
        .add_execute('echo "Success"', description="Success Command")
        .build()
    )
    result = cli.run_execute_with_plan(plan)

    assert "SUCCESS" in result.stdout
    assert "FAILURE" not in result.stdout


def test_cli_granular_execution_logs(tmp_path, monkeypatch):
    """
    Scenario: Verify that execution logs show specific action types.
    """
    TestEnvironment(monkeypatch, tmp_path).setup()
    cli = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Logs Test")
        .add_create("test.txt", "content", description="Log test")
        .build()
    )
    result = cli.run_execute_with_plan(plan)

    assert "CREATE" in result.stdout
    assert "Log test" in result.stdout
