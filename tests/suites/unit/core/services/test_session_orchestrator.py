from unittest.mock import MagicMock
import pytest
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.services.session_planner import SessionPlanner
from teddy_executor.core.services.session_replanner import SessionReplanner
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


@pytest.fixture
def orchestrator(  # noqa: PLR0913
    container,
    mock_run_plan,
    mock_session_manager,
    mock_fs,
    mock_report_formatter,
    mock_plan_validator,
    mock_planning_service,
    mock_plan_parser,
    mock_user_interactor,
    mock_context_service,
):
    # Manually instantiate sub-services using the container to resolve ports
    replanner = SessionReplanner(
        file_system_manager=container.resolve(IFileSystemManager),
        planning_service=container.resolve(IPlanningUseCase),
    )
    session_planner = SessionPlanner(
        file_system_manager=container.resolve(IFileSystemManager),
        planning_service=container.resolve(IPlanningUseCase),
        user_interactor=container.resolve(IUserInteractor),
        session_service=container.resolve(ISessionManager),
    )

    # Instantiate the orchestrator with its dependencies
    orchestrator_instance = SessionOrchestrator(
        execution_orchestrator=container.resolve(IRunPlanUseCase),
        session_service=container.resolve(ISessionManager),
        file_system_manager=container.resolve(IFileSystemManager),
        report_formatter=container.resolve(IMarkdownReportFormatter),
        plan_validator=container.resolve(IPlanValidator),
        planning_service=container.resolve(IPlanningUseCase),
        plan_parser=container.resolve(IPlanParser),
        user_interactor=container.resolve(IUserInteractor),
        replanner=replanner,
        session_planner=session_planner,
    )

    # Register as instances to bypass punq auto-wiring for untyped constructors
    container.register(SessionReplanner, instance=replanner)
    container.register(SessionPlanner, instance=session_planner)
    container.register(SessionOrchestrator, instance=orchestrator_instance)

    return container.resolve(SessionOrchestrator)


def test_session_orchestrator_triggers_transition_on_success(  # noqa: PLR0913
    orchestrator,
    mock_run_plan,
    mock_session_manager,
    mock_fs,
    mock_plan_parser,
    mock_plan_validator,
):
    """
    SessionOrchestrator should call SessionService.transition_to_next_turn
    after successful plan execution.
    """
    # Arrange
    # Mock successful execution
    mock_run_plan.execute.return_value = MagicMock()  # ExecutionReport

    plan_content = MarkdownPlanBuilder("Test").build()
    plan_path = "path/to/01/plan.md"
    meta_content = "agent_name: pathfinder\ncumulative_cost: 0.0\nturn_cost: 0.0"

    def read_file_side_effect(path):
        if "meta.yaml" in str(path):
            return meta_content
        return plan_content

    mock_fs.read_file.side_effect = read_file_side_effect
    mock_fs.path_exists.return_value = True

    # Mock parsing and validation to allow execution flow
    mock_plan_parser.parse.return_value = MagicMock()
    mock_plan_validator.validate.return_value = []

    # Act
    orchestrator.execute(plan_content=plan_content, plan_path=plan_path)

    # Assert
    # Verify execution was called
    mock_run_plan.execute.assert_called_once()

    # Verify transition was called with the plan path and cost
    mock_session_manager.transition_to_next_turn.assert_called_once_with(
        plan_path=plan_path,
        execution_report=mock_run_plan.execute.return_value,
        is_validation_failure=False,
        turn_cost=0.0,
    )
