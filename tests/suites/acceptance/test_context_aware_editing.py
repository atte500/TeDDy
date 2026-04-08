import os
import asyncio
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.drivers.tui_driver import TuiDriver
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
from teddy_executor.core.ports.outbound import ISystemEnvironment, IFileSystemManager


def test_tui_context_aware_editing_marks_action_as_modified(env):
    """Scenario: Verify that editing a CREATE action in the TUI marks it as modified in the report."""
    # Arrange: Create a plan with a CREATE action
    # Assuming standard names based on pattern: .rationale(), .create(...)
    plan_content = (
        MarkdownPlanBuilder("TUI Modification Test")
        .add_create(
            path="new_file.py",
            description="Create a new script",
            content="print('original')",
        )
        .build()
    )
    env.with_real_filesystem().with_real_system_environment()

    # 2. Arrange: Create a plan with a CREATE action
    plan_content = (
        MarkdownPlanBuilder("TUI Modification Test")
        .add_create(
            path="new_file.py",
            description="Create a new script",
            content="print('original')",
        )
        .build()
    )

    # 3. Parse Plan
    parser = MarkdownPlanParser()
    plan = parser.parse(plan_content)

    # 4. Mock the editor output for the TUI hook
    os.environ["TEDDY_TEST_MOCK_EDITOR_OUTPUT"] = "print('modified')"

    try:
        # 5. Act: Simulate TUI Interaction ('p' triggers preview/edit, 's' submits)
        driver = TuiDriver(
            plan=plan,
            system_env=env.get_service(ISystemEnvironment),
            file_system=env.get_service(IFileSystemManager),
        )

        # Run interaction (down, e, then modal sequence: y, then submit: s)
        modified_plan = asyncio.run(driver.run_interaction(["down", "e", "y", "s"]))
        assert modified_plan is not None

        # 6. Execute modified plan through orchestrator
        orchestrator = env.get_service(ExecutionOrchestrator)
        report = orchestrator.execute(modified_plan, interactive=False)

        # 7. Assert: File created with modified content
        assert (env.workspace / "new_file.py").read_text() == "print('modified')"

        # 8. Verify the report contains the (modified) tag
        from teddy_executor.core.ports.outbound import IMarkdownReportFormatter

        formatter = env.get_service(IMarkdownReportFormatter)
        report_content = formatter.format(report)
        assert "### `CREATE` (modified): [new_file.py](/new_file.py)" in report_content

    finally:
        os.environ.pop("TEDDY_TEST_MOCK_EDITOR_OUTPUT", None)
