from tests.setup.test_environment import TestEnvironment
from tests.drivers.cli_adapter import CliTestAdapter
from tests.drivers.plan_builder import MarkdownPlanBuilder


def test_isolated_terminal_action_executes_normally(tmp_path, monkeypatch):
    """Scenario 1: Isolated Terminal Action executes normally."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Isolated Prompt")
        .add_prompt("Please confirm this isolated prompt.")
        .build()
    )

    report = adapter.execute_plan(plan, user_input="y\n")

    assert report.action_was_successful(0)
    assert report.action_logs[0].type == "PROMPT"
    assert report.action_logs[0].status == "SUCCESS"


def test_terminal_action_is_skipped_in_multi_action_plan(tmp_path, monkeypatch):
    """Scenario 2: Terminal Action is skipped in multi-action plan."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    filename = "new_file.txt"
    plan = (
        MarkdownPlanBuilder("Multi-action Plan")
        .add_create(filename, "File content.")
        .add_prompt("Please confirm this non-isolated prompt.")
        .build()
    )

    # Use adapter to execute. Isolation logic should skip the PROMPT.
    report = adapter.execute_plan(plan)

    # CREATE should succeed
    assert report.action_was_successful(0)
    assert (tmp_path / filename).exists()

    # PROMPT should be SKIPPED
    assert report.action_logs[1].type == "PROMPT"
    assert report.action_logs[1].status == "SKIPPED"
    assert "Action must be executed in isolation to ensure state consistency." in str(
        report.action_logs[1].params
    )
