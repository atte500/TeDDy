from teddy_executor.core.domain.models import ActionStatus, RunStatus
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


# env fixture is now provided globally from tests/conftest.py


def test_execute_handles_valid_plan_successfully(env):
    """
    Given a valid plan,
    When the ExecutionOrchestrator is invoked,
    Then it should return a SUCCESS report.
    """
    orchestrator = env.get_service(IRunPlanUseCase)

    plan_content = (
        MarkdownPlanBuilder("Valid Plan")
        .add_create(
            path="file1.txt",
            content="content1",
            overwrite=True,
            description="First file",
        )
        .build()
    )

    # Act
    report = orchestrator.execute(plan_content=plan_content, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    assert report.action_logs[0].status == ActionStatus.SUCCESS


def test_orchestrator_skips_terminal_action_in_multi_action_plan_integration(env):
    """
    Scenario: Orchestrator skips terminal actions when part of a multi-action plan.
    """
    orchestrator = env.get_service(IRunPlanUseCase)

    plan_content = (
        MarkdownPlanBuilder("Isolation Test")
        .add_execute("ls", description="Listing files")
        .add_prompt("Please confirm this prompt.")
        .build()
    )

    # Act
    report = orchestrator.execute(plan_content=plan_content, interactive=False)

    # Assert
    assert len(report.action_logs) == 2  # noqa: PLR2004
    # First action (EXECUTE) should succeed (mocked shell returns success by default)
    assert report.action_logs[0].action_type == "EXECUTE"
    assert report.action_logs[0].status == ActionStatus.SUCCESS

    # Second action (PROMPT) should be SKIPPED by orchestrator logic
    assert report.action_logs[1].action_type == "PROMPT"
    assert report.action_logs[1].status == ActionStatus.SKIPPED
    assert "Action must be executed in isolation" in str(report.action_logs[1].details)


def test_orchestrator_skips_invoke_in_multi_action_plan_integration(env):
    """
    Scenario: Orchestrator skips INVOKE actions when part of a multi-action plan.
    """
    orchestrator = env.get_service(IRunPlanUseCase)

    plan_content = (
        MarkdownPlanBuilder("INVOKE Isolation Test")
        .add_execute("ls", description="Listing files")
        .add_invoke(agent="Architect", description="Moving to design phase")
        .build()
    )

    # Act
    report = orchestrator.execute(plan_content=plan_content, interactive=False)

    # Assert
    assert len(report.action_logs) == 2  # noqa: PLR2004
    assert report.action_logs[0].action_type == "EXECUTE"
    assert report.action_logs[0].status == ActionStatus.SUCCESS

    # Second action (INVOKE) should be SKIPPED
    assert report.action_logs[1].action_type == "INVOKE"
    assert report.action_logs[1].status == ActionStatus.SKIPPED
    assert "Action must be executed in isolation" in str(report.action_logs[1].details)
