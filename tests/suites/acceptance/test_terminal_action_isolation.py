import pytest
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


import os


def test_terminal_action_skipped_in_multi_action_non_interactive_plan(
    real_env: TestEnvironment, monkeypatch
):
    """
    GIVEN a plan containing a "PROMPT" action and a "CREATE" action
    AND the execution mode is non-interactive
    WHEN I execute the plan
    THEN the "PROMPT" action should be skipped
    AND the reason should be "these actions should be executed in isolation"
    """
    # 1. Setup (Arrange)
    assert real_env.workspace
    monkeypatch.chdir(real_env.workspace)
    adapter = CliTestAdapter(monkeypatch, real_env.workspace)

    unique_file = "test_data/iso_test_primary.txt"
    plan_content = (
        MarkdownPlanBuilder(title="Mixed Plan")
        .add_create(path=unique_file, content="hello", overwrite=True)
        .add_prompt(message="Should be skipped")
        .build()
    )

    # 2. Driver (Act)
    report = adapter.execute_plan(plan_content=plan_content)

    # 3. Observer (Assert)
    prompt_log = next(log for log in report.action_logs if log.type == "PROMPT")

    assert prompt_log.status == "SKIPPED"
    # Skip Reason is captured in params by the ReportParser
    assert (
        prompt_log.params.get("Skip Reason")
        == "these actions should be executed in isolation"
    )

    # Secondary Guard: Verify no debris in the ACTUAL project root
    assert not os.path.exists(unique_file), "Debris detected in project root!"


@pytest.mark.parametrize("action_type", ["INVOKE", "RETURN"])
def test_other_terminal_actions_follow_isolation_rule(
    real_env: TestEnvironment, monkeypatch, action_type: str
):
    """Verify INVOKE and RETURN also use the new isolation reason."""
    assert real_env.workspace
    monkeypatch.chdir(real_env.workspace)
    adapter = CliTestAdapter(monkeypatch, real_env.workspace)

    unique_file = f"test_data/iso_test_{action_type.lower()}.py"
    builder = MarkdownPlanBuilder(title="Handoff Plan").add_create(
        path=unique_file, content="# foo", overwrite=True
    )

    if action_type == "INVOKE":
        builder.add_invoke(agent="Pathfinder", description="Explore")
    else:
        builder.add_return(description="Done")

    plan_content = builder.build()
    report = adapter.execute_plan(plan_content=plan_content)

    terminal_log = next(log for log in report.action_logs if log.type == action_type)

    assert terminal_log.status == "SKIPPED"
    assert (
        terminal_log.params.get("Skip Reason")
        == "these actions should be executed in isolation"
    )

    # Secondary Guard: Verify no debris in the ACTUAL project root
    assert not os.path.exists(unique_file), "Debris detected in project root!"


# NOTE: Deselection reason is verified at the Unit level in:
# tests/suites/unit/core/services/test_terminal_action_deselection.py
