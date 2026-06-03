"""Acceptance tests for EDIT mid-execution consistency checking."""

from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.observers.report_parser import ReportParser


def test_edit_fails_when_file_modified_by_preceding_execute(monkeypatch, tmp_path):
    """
    Scenario: EXECUTE modifies a file → subsequent EDIT with stale FIND → FAILURE.
    Verifies that the CLI correctly reports failure when an EDIT targets content
    that was changed by an earlier EXECUTE in the same plan.
    """
    # Arrange: Set up real filesystem and shell
    env = TestEnvironment(monkeypatch, tmp_path).setup()
    env.with_real_filesystem()
    env.with_real_shell()

    # Create a file with known content
    target_file = tmp_path / "target.py"
    target_file.write_text("original content\n", encoding="utf-8")

    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Build a plan: EXECUTE modifies the file, then EDIT tries to match old content
    plan = (
        MarkdownPlanBuilder("Mid-Execution Edit Consistency")
        .add_execute(
            f'echo "modified content" > "{target_file}"',
            description="Change file content externally",
        )
        .add_edit(
            path="target.py",
            find_replace="original content",
            replace="patched content",
            description="Attempt edit with stale FIND",
        )
        .build()
    )

    # Act: Execute the plan non-interactively
    result = adapter.run_execute_with_plan(plan_content=plan)

    # Assert
    assert result.exit_code == 1, "CLI should exit with failure code"

    report = ReportParser(result.stdout + result.stderr)

    # First action (EXECUTE) should succeed
    assert report.action_logs[0].type == "EXECUTE"
    assert report.action_logs[0].status == "SUCCESS"

    # Second action (EDIT) should fail - either via hash pre-check or FIND mismatch
    assert report.action_logs[1].type == "EDIT"
    assert report.action_logs[1].status == "FAILURE"


def test_edit_fails_when_file_externally_modified_between_two_edits(
    monkeypatch, tmp_path
):
    """
    Scenario: Two EDITs on the same file with external modification between them → FAILURE.
    This tests the hash pre-check path in ActionExecutor.
    """
    # Arrange: Set up real filesystem and shell
    env = TestEnvironment(monkeypatch, tmp_path).setup()
    env.with_real_filesystem()
    env.with_real_shell()

    # Create a file with known content
    target_file = tmp_path / "target.py"
    target_file.write_text("original content\nfirst section\n", encoding="utf-8")

    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Build a plan: first EDIT changes "original content", then EXECUTE modifies file,
    # then second EDIT tries to change "first section" (now stale)
    plan = (
        MarkdownPlanBuilder("Mid-Execution Edit Consistency - Two Edits")
        .add_edit(
            path="target.py",
            find_replace="original content",
            replace="patched content",
            description="First edit (should succeed)",
        )
        .add_execute(
            f'echo "modified content" > "{target_file}"',
            description="Change file content externally",
        )
        .add_edit(
            path="target.py",
            find_replace="first section",
            replace="updated section",
            description="Second edit after external change",
        )
        .build()
    )

    # Act: Execute the plan non-interactively
    result = adapter.run_execute_with_plan(plan_content=plan)

    # Assert
    assert result.exit_code == 1, "CLI should exit with failure code"

    report = ReportParser(result.stdout + result.stderr)

    # First EDIT should succeed
    assert report.action_logs[0].status == "SUCCESS"

    # EXECUTE should succeed
    assert report.action_logs[1].type == "EXECUTE"
    assert report.action_logs[1].status == "SUCCESS"

    # Second EDIT should fail
    assert report.action_logs[2].type == "EDIT"
    assert report.action_logs[2].status == "FAILURE"
