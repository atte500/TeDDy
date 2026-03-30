import os
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


def test_tui_context_aware_editing_marks_action_as_modified(cli, env):
    """Scenario: Verify that editing a CREATE action in the TUI marks it as modified in the report."""
    # Arrange: Create a plan with a CREATE action
    plan_content = (
        MarkdownPlanBuilder()
        .with_title("TUI Modification Test")
        .with_rationale("Testing context aware editing.")
        .add_create_action(
            path="new_file.py",
            description="Create a new script",
            content="print('original')",
        )
        .build()
    )
    env.write_file("plan.md", plan_content)

    # Mock the editor output for the TUI hook
    os.environ["TEDDY_TEST_MOCK_EDITOR_OUTPUT"] = "print('modified')"

    try:
        # Act: Run execute in interactive mode
        # 'p' triggers preview, which uses the mock editor output
        # 's' submits the plan
        result = cli.run("execute plan.md --interactive", input_keys="ps")

        # Assert
        assert result.exit_code == 0
        assert (env.root / "new_file.py").read_text() == "print('modified')"

        # Verify the report contains the (modified) tag
        report_content = env.read_file(".teddy/sessions/last/01/report.md")
        assert "### `CREATE` (modified): [new_file.py](/new_file.py)" in report_content
    finally:
        if "TEDDY_TEST_MOCK_EDITOR_OUTPUT" in os.environ:
            del os.environ["TEDDY_TEST_MOCK_EDITOR_OUTPUT"]
