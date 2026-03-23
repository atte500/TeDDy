import pytest
from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


def test_ui_mode_console_uses_sequential_reviewer(tmp_path, monkeypatch):
    """Scenario: UI Mode Toggling (TUI vs. Console) - Sequential prompting."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_interactor()

    adapter = CliTestAdapter(monkeypatch, tmp_path)
    plan = MarkdownPlanBuilder("Test Plan").add_create("test.txt", "content").build()

    # We expect this to fail because the --no-tui flag and wiring are not yet implemented.
    with pytest.raises(Exception):
        adapter.execute_plan(
            plan, user_input="y\n", interactive=True, extra_args=["--no-tui"]
        )
