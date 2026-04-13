from pathlib import Path

import pytest
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


def test_terminal_action_skipped_in_multi_action_non_interactive_plan(
    real_env: TestEnvironment, monkeypatch
):
    """
    GIVEN a plan containing a "PROMPT" action and a "CREATE" action
    AND the execution mode is non-interactive
    WHEN I execute the plan
    THEN the "PROMPT" action should be skipped
    AND the reason should be "Automatically skipped: This action must be performed in isolation."
    """
    # 1. Setup (Arrange)
    assert real_env.workspace
    monkeypatch.chdir(real_env.workspace)
    adapter = CliTestAdapter(monkeypatch, real_env.workspace)

    unique_file = "test_data/iso_test_primary.txt"

    # Cleanup stale debris from previous failed runs
    real_project_root = Path(__file__).resolve().parents[3]
    stale_file = real_project_root / unique_file
    if stale_file.exists():
        stale_file.unlink()
    plan_content = (
        MarkdownPlanBuilder(title="Mixed Plan")
        .add_create(path=unique_file, content="hello", overwrite=True)
        .add_prompt(message="Should be skipped")
        .build()
    )

    # 2. Driver (Act)
    report = adapter.execute_plan(plan_content=plan_content)

    # 3. Observer (Assert)
    # CRITICAL: Verify the non-terminal action actually occurred in the real workspace.
    # If this fails, the system is using the Mock FS instead of the Real FS.
    absolute_file_path = real_env.workspace / unique_file
    assert absolute_file_path.exists(), (
        f"File should have been created at {absolute_file_path}"
    )

    prompt_log = next(log for log in report.action_logs if log.type == "PROMPT")

    assert prompt_log.status == "SKIPPED"
    # Skip Reason is captured in params by the ReportParser
    assert (
        prompt_log.params.get("Skip Reason")
        == "Automatically skipped: This action must be performed in isolation."
    )

    # Secondary Guard: Verify no debris in the DEVELOPER'S project root
    # We find the real project root relative to this test file to avoid workspace confusion.
    real_project_root = Path(__file__).resolve().parents[3]
    project_root_file = (real_project_root / unique_file).resolve()
    assert not project_root_file.exists(), (
        f"Debris detected in project root: {project_root_file}"
    )


@pytest.mark.parametrize("action_type", ["INVOKE", "RETURN"])
def test_other_terminal_actions_follow_isolation_rule(
    real_env: TestEnvironment, monkeypatch, action_type: str
):
    """Verify INVOKE and RETURN also use the new isolation reason."""
    assert real_env.workspace
    monkeypatch.chdir(real_env.workspace)
    adapter = CliTestAdapter(monkeypatch, real_env.workspace)

    unique_file = f"test_data/iso_test_{action_type.lower()}.py"

    # Cleanup stale debris from previous failed runs
    real_project_root = Path(__file__).resolve().parents[3]
    stale_file = real_project_root / unique_file
    if stale_file.exists():
        stale_file.unlink()

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
        == "Automatically skipped: This action must be performed in isolation."
    )

    # Secondary Guard: Verify no debris in the DEVELOPER'S project root
    # We find the real project root relative to this test file to avoid workspace confusion.
    real_project_root = Path(__file__).resolve().parents[3]
    project_root_file = (real_project_root / unique_file).resolve()
    assert not project_root_file.exists(), (
        f"Debris detected in project root: {project_root_file}"
    )


# NOTE: Deselection reason is verified at the Unit level in:
# tests/suites/unit/core/services/test_terminal_action_deselection.py
