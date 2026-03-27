from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


def test_ui_mode_console_uses_sequential_reviewer(tmp_path, monkeypatch):
    """Scenario: UI Mode Toggling (TUI vs. Console) - Sequential prompting."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_interactor()

    adapter = CliTestAdapter(monkeypatch, tmp_path)
    plan = MarkdownPlanBuilder("Test Plan").add_create("test.txt", "content").build()

    # Run in console mode.
    # Since TestEnvironment registers IPlanReviewer=None,
    # the CLI flag should override it and use ConsolePlanReviewer.
    # We now skip the bulk summary and go straight to the action prompt.
    report = adapter.execute_plan(
        plan, user_input="y\n", interactive=True, extra_args=["--console"]
    )

    # ReportParser uses the run_summary dict.
    # The template uses "Overall Status".
    status_val = report.run_summary.get("Overall Status") or report.run_summary.get(
        "Status"
    )
    assert "SUCCESS" in status_val.upper()
    # Verify that the console reviewer was used by checking for the action-level prompt.
    assert "Approve? (y/n/m):" in report.stdout
