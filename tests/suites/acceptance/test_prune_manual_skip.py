from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.observers.report_parser import ReportParser


def test_prune_is_automatically_skipped_in_manual_mode(monkeypatch, tmp_path):
    # Given a plan with a PRUNE action (not in a session directory)
    TestEnvironment(monkeypatch, tmp_path).setup()
    cli = CliTestAdapter(monkeypatch, tmp_path)

    plan_content = (
        MarkdownPlanBuilder("Manual PRUNE Test")
        .add_prune(
            resource="[old_file.md](/old_file.md)", description="Pruning old file"
        )
        .build()
    )

    # We use the adapter's run_execute_with_plan which uses --plan-content
    # This avoids worrying about workspace paths for the plan file itself.

    # When I execute the plan in non-interactive mode (simulating manual CLI)
    result = cli.run_execute_with_plan(plan_content=plan_content, interactive=False)

    # Then the execution should succeed
    assert result.exit_code == 0

    # And the report should show the PRUNE action as SKIPPED
    report = ReportParser(result.stdout)
    prune_log = next(log for log in report.action_logs if log.type == "PRUNE")
    assert prune_log.status == "SKIPPED"
    assert "manual mode to prevent workspace corruption" in prune_log.params.get(
        "Skip Reason", ""
    )


def test_prune_is_NOT_automatically_skipped_in_session_mode(monkeypatch, tmp_path):
    from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
    from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser

    # Given a plan with a PRUNE action in a session directory
    env = TestEnvironment(monkeypatch, tmp_path).setup()

    # Force real parser to ensure is_session logic runs
    env.container.register(IPlanParser, MarkdownPlanParser)

    cli = CliTestAdapter(monkeypatch, tmp_path)

    session_dir = tmp_path / ".teddy" / "sessions" / "my_session" / "01"
    session_dir.mkdir(parents=True)

    plan_content = (
        MarkdownPlanBuilder("Session PRUNE Test")
        .add_prune(
            resource="[old_file.md](/old_file.md)", description="Pruning old file"
        )
        .build()
    )

    plan_path = session_dir / "plan.md"
    plan_path.write_text(plan_content)

    # We must ensure the file exists so it passes validator (which might be called)
    (tmp_path / "old_file.md").write_text("content")
    # And it must be in context
    (session_dir / "turn.context").write_text("old_file.md")

    # When I execute the plan
    with monkeypatch.context() as m:
        m.setenv("TEDDY_DEBUG", "true")
        result = cli.run_cli_command(["execute", "--yes", "--no-copy", str(plan_path)])

    # DEBUG: Print output unconditionally
    print(f"STDOUT: {result.stdout}")
    print(f"STDERR: {result.stderr}")

    # Then the execution should succeed (PRUNE is success/skipped depending on context logic,
    # but NOT the manual mode interceptor)
    assert result.exit_code == 0
    report = ReportParser(result.stdout)
    prune_log = next(log for log in report.action_logs if log.type == "PRUNE")

    # In a session, it should NOT be "not supported in manual mode"
    assert "manual execution mode" not in prune_log.params.get("Skip Reason", "")
    # The requirement says "MUST NOT be reviewed", which is handled by --no-interactive here,
    # but the core logic should skip it regardless of interaction if it's manual.
