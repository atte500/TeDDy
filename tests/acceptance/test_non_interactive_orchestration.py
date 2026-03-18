from tests.setup.test_environment import TestEnvironment
from tests.drivers.cli_adapter import CliTestAdapter
from tests.drivers.plan_builder import MarkdownPlanBuilder
from tests.observers.report_parser import ReportParser


def test_prune_auto_skipped_in_non_interactive_mode(tmp_path, monkeypatch):
    """Scenario 1: PRUNE is auto-skipped in non-interactive (manual) mode."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Prune Plan")
        .add_prune("dummy.txt", "Remove dummy from context.")
        .build()
    )

    # Execute with --yes (interactive=False)
    report = adapter.execute_plan(plan, interactive=False)

    # Check status and reason (stored in params['Skip Reason'])
    assert report.action_logs[0].status == "SKIPPED"
    assert (
        "PRUNE is not supported in manual execution mode"
        in report.action_logs[0].params["Skip Reason"]
    )


def test_invoke_interactive_approval(tmp_path, monkeypatch):
    """Scenario 2 (Interactive): INVOKE with interactive approval should succeed."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    env.with_real_interactor()  # Need real interactor for stderr and stdin
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Invoke Plan")
        .add_invoke(
            "Architect", "Handoff to the Architect.", reference_files=["docs/spec.md"]
        )
        .build()
    )

    # Test interactive mode: user approves by pressing Enter
    result = adapter.run_execute_with_plan(plan, interactive=True, input="\n")

    assert result.exit_code == 0
    # Verify the manual handoff instruction block in stderr (where interactor prints)
    assert "HANDOFF REQUEST" in result.stderr
    assert "Target Agent: Architect" in result.stderr
    assert "docs/spec.md" in result.stderr

    # Verify report via parser
    report = ReportParser(result.stdout)
    assert report.action_logs[0].status == "SUCCESS"
    assert report.action_logs[0].type == "INVOKE"
    assert "Architect" in report.action_logs[0].params["Description"]
    assert "[docs/spec.md](/docs/spec.md)" in result.stdout


def test_invoke_non_interactive_must_interrupt(tmp_path, monkeypatch):
    """Scenario 2 (--yes): INVOKE with --yes flag should still interrupt and prompt."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    env.with_real_interactor()  # Need real interactor for stderr and stdin
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Invoke Plan")
        .add_invoke("Architect", "Handoff to the Architect.")
        .build()
    )

    # Even with --yes (interactive=False), it should prompt for input.
    result = adapter.run_execute_with_plan(plan, interactive=False, input="\n")

    assert result.exit_code == 0
    assert "HANDOFF REQUEST" in result.stderr
    assert ReportParser(result.stdout).action_logs[0].status == "SUCCESS"


def test_invoke_rejected_in_non_interactive_mode(tmp_path, monkeypatch):
    """Scenario 2 (Rejection): INVOKE rejected with reason becomes FAILURE."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    env.with_real_interactor()  # Need real interactor for stderr and stdin
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Invoke Plan")
        .add_invoke("Architect", "Handoff to the Architect.")
        .build()
    )

    rejection_reason = "Not ready for architect yet."
    result = adapter.run_execute_with_plan(
        plan, interactive=True, input=rejection_reason + "\n"
    )

    # It should fail overall because an action failed
    assert result.exit_code == 1

    report = ReportParser(result.stdout)
    assert report.action_logs[0].status == "FAILURE"
    assert (
        f"Manual handoff rejected by user: {rejection_reason}"
        in report.action_logs[0].details["details"]
    )
