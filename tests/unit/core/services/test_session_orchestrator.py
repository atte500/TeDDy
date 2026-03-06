from unittest.mock import MagicMock
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator


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

    orchestrator = SessionOrchestrator(
        execution_orchestrator=execution_orchestrator,
        session_service=session_service,
        file_system_manager=MagicMock(),
        report_formatter=MagicMock(),
    )

    plan_content = "some plan"
    plan_path = "path/to/01/plan.md"

    # Act
    orchestrator.execute(plan_content=plan_content, plan_path=plan_path)

    # Assert
    # Verify execution was called
    execution_orchestrator.execute.assert_called_once()

    # Verify transition was called with the plan path
    session_service.transition_to_next_turn.assert_called_once_with(
        plan_path=plan_path,
        execution_report=execution_orchestrator.execute.return_value,
    )
