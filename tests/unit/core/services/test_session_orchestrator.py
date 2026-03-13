from unittest.mock import MagicMock
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.services.session_planner import SessionPlanner
from teddy_executor.core.services.session_replanner import SessionReplanner


def test_session_orchestrator_triggers_transition_on_success():
    """
    SessionOrchestrator should call SessionService.transition_to_next_turn
    after successful plan execution.
    """
    # Arrange
    execution_orchestrator = MagicMock()
    session_service = MagicMock()

    # Mock successful execution
    execution_orchestrator.execute.return_value = MagicMock()  # ExecutionReport

    file_system_manager = MagicMock()
    file_system_manager.read_file.return_value = (
        "agent_name: pathfinder\ncumulative_cost: 0.0\nturn_cost: 0.0"
    )

    planning_service = MagicMock()
    user_interactor = MagicMock()
    orchestrator = SessionOrchestrator(
        execution_orchestrator=execution_orchestrator,
        session_service=session_service,
        file_system_manager=file_system_manager,
        report_formatter=MagicMock(),
        plan_validator=MagicMock(),
        planning_service=planning_service,
        plan_parser=MagicMock(),
        user_interactor=user_interactor,
        replanner=SessionReplanner(file_system_manager, planning_service),
        session_planner=SessionPlanner(
            file_system_manager, planning_service, user_interactor, session_service
        ),
    )

    plan_content = "some plan"
    plan_path = "path/to/01/plan.md"

    # Mock parsing and validation to allow execution flow
    orchestrator._plan_parser.parse.return_value = MagicMock()
    orchestrator._plan_validator.validate.return_value = []

    # Act
    orchestrator.execute(plan_content=plan_content, plan_path=plan_path)

    # Assert
    # Verify execution was called
    execution_orchestrator.execute.assert_called_once()

    # Verify transition was called with the plan path and cost
    session_service.transition_to_next_turn.assert_called_once_with(
        plan_path=plan_path,
        execution_report=execution_orchestrator.execute.return_value,
        is_validation_failure=False,
        turn_cost=0.0,
    )
