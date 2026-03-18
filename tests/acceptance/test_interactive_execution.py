from tests.setup.test_environment import TestEnvironment
from tests.drivers.cli_adapter import CliTestAdapter
from tests.drivers.plan_builder import MarkdownPlanBuilder


def test_interactive_execution_accept_all(tmp_path, monkeypatch):
    """Scenario: User accepts all actions in an interactive session."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Interactive Plan")
        .add_create("hello.txt", "Hello World!")
        .add_execute('echo "Command executed"')
        .build()
    )

    # y for CREATE, y for EXECUTE
    report = adapter.execute_plan(plan, user_input="y\ny\n", interactive=True)

    assert report.action_was_successful(0) is True
    assert report.action_was_successful(1) is True
    assert report.run_summary["Overall Status"] == "SUCCESS"
    assert (tmp_path / "hello.txt").exists()


def test_interactive_execution_skip_one(tmp_path, monkeypatch):
    """Scenario: User skips one action in an interactive session."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Interactive Plan")
        .add_create("hello.txt", "Hello World!")
        .add_execute('echo "This should be skipped"')
        .build()
    )

    # y for CREATE, n for EXECUTE (then empty reason)
    report = adapter.execute_plan(plan, user_input="y\nn\n\n", interactive=True)

    assert report.action_was_successful(0) is True
    assert report.action_logs[1].status == "SKIPPED"
    # Note: System reports SUCCESS if no failures occurred, even with skips.
    assert report.run_summary["Overall Status"] == "SUCCESS"
    assert (tmp_path / "hello.txt").exists()


def test_interactive_skip_with_reason(tmp_path, monkeypatch):
    """Scenario: User skips an action with a specific reason."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Interactive Skip with Reason")
        .add_create("test.txt", "Should not exist")
        .build()
    )

    # n for CREATE, then "Manual check needed" as reason
    report = adapter.execute_plan(
        plan, user_input="n\nManual check needed\n", interactive=True
    )

    assert report.action_logs[0].status == "SKIPPED"
    # Reason is parsed into params by ReportParser
    assert "Manual check needed" in report.action_logs[0].params["Skip Reason"]
    assert not (tmp_path / "test.txt").exists()
