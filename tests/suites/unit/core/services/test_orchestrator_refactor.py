from unittest.mock import Mock
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
from teddy_executor.core.domain.models.orchestrator_ports import OrchestratorPorts


def test_orchestrator_can_be_initialized_with_ports():
    # Arrange
    ports = OrchestratorPorts(
        plan_parser=Mock(),
        plan_validator=Mock(),
        action_executor=Mock(),
        file_system_manager=Mock(),
        report_assembler=Mock(),
        user_interactor=Mock(),
        plan_reviewer=Mock(),
    )

    # Act
    # This should fail because __init__ still expects 7 individual args
    orchestrator = ExecutionOrchestrator(ports=ports)

    # Assert
    assert orchestrator._plan_parser == ports.plan_parser
