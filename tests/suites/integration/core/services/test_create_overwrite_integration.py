from teddy_executor.core.domain.models import RunStatus, ActionStatus
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.setup.test_environment import TestEnvironment


def test_create_passes_if_file_exists_with_overwrite_integration(tmp_path, monkeypatch):
    """
    Integration test ensuring CREATE action with Overwrite: true correctly
    overwrites an existing file at the service layer using a real filesystem.
    """
    # Arrange: Setup anchored environment (handles real FS registration)
    env = TestEnvironment(monkeypatch, workspace=tmp_path).setup()
    parser = env.get_service(IPlanParser)
    orchestrator = env.get_service(IRunPlanUseCase)

    # Pre-seed the real filesystem
    existing_file = tmp_path / "existing.txt"
    existing_file.write_text("original content", encoding="utf-8")

    # Use Driver (MarkdownPlanBuilder) to create a valid plan
    plan_content = (
        MarkdownPlanBuilder("Overwrite Test")
        .add_create(
            path="existing.txt",
            content="new content",
            overwrite=True,
            description="Overwrite existing file",
        )
        .build()
    )
    plan = parser.parse(plan_content)

    # Act
    report = orchestrator.execute(plan=plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    assert report.action_logs[0].status == ActionStatus.SUCCESS

    # Verify real-world side effect
    assert existing_file.read_text(encoding="utf-8") == "new content"

    # Verify the report includes the diff (Scenario 3 requirement)
    action_log = report.action_logs[0]
    assert "diff" in action_log.details
    assert "--- a/existing.txt" in action_log.details["diff"]
    assert "+new content" in action_log.details["diff"]
