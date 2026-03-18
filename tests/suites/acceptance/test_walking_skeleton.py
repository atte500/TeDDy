from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.observers.report_parser import ReportParser


def test_successful_execution(tmp_path, monkeypatch):
    """Scenario: Valid plan with echo succeeds."""
    TestEnvironment(monkeypatch, tmp_path).setup().with_real_shell()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Success")
        .add_execute("echo 'hello world'", description="Echo hello")
        .build()
    )

    result = adapter.run_execute_with_plan(plan_content=plan)

    assert result.exit_code == 0
    report = ReportParser(result.stdout)
    assert report.run_summary["Overall Status"] == "SUCCESS"
    assert "hello world" in report.action_logs[0].details["stdout"]


def test_failed_execution(tmp_path, monkeypatch):
    """Scenario: Failing command returns non-zero and marks failure."""
    TestEnvironment(monkeypatch, tmp_path).setup().with_real_shell()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    plan = MarkdownPlanBuilder("Failure").add_execute("nonexistentcommand12345").build()

    result = adapter.run_execute_with_plan(plan_content=plan)

    assert result.exit_code == 1
    report = ReportParser(result.stdout)
    assert report.run_summary["Overall Status"] == "FAILURE"
    assert report.action_logs[0].status == "FAILURE"
