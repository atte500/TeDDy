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


def _assert_first_action_is_successful_execute(report):
    """Helper to assert the first action is a successful EXECUTE."""
    expected_logs = 2
    assert len(report.action_logs) == expected_logs
    assert report.action_logs[0].action_type == "EXECUTE"
    assert report.action_logs[0].status == ActionStatus.SUCCESS
