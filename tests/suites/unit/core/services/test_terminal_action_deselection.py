from unittest.mock import Mock
from teddy_executor.core.domain.models import ActionData, Plan
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
from teddy_executor.core.domain.models.orchestrator_ports import OrchestratorPorts


def test_deselected_terminal_action_uses_isolation_reason():
    # Setup
    executor = Mock()
    orchestrator = ExecutionOrchestrator(
        ports=OrchestratorPorts(
            plan_parser=Mock(),
            plan_validator=Mock(),
            action_executor=executor,
            file_system_manager=Mock(),
            report_assembler=Mock(),
            user_interactor=Mock(),
        )
    )

    # Action marked as NOT selected
    action = ActionData(type="PROMPT", params={"prompt": "test"}, selected=False)
    plan = Plan(title="Test", rationale="Test", actions=[action])

    # Act
    orchestrator._process_plan_actions(plan, interactive=False)

    # Assert
    executor.handle_skipped_action.assert_called_with(
        action, "Automatically skipped: This action must be performed in isolation."
    )


def test_deselected_non_terminal_action_uses_standard_reason():
    # Setup
    executor = Mock()
    orchestrator = ExecutionOrchestrator(
        ports=OrchestratorPorts(
            plan_parser=Mock(),
            plan_validator=Mock(),
            action_executor=executor,
            file_system_manager=Mock(),
            report_assembler=Mock(),
            user_interactor=Mock(),
        )
    )

    # Non-terminal action marked as NOT selected
    action = ActionData(type="CREATE", params={"path": "foo"}, selected=False)
    plan = Plan(title="Test", rationale="Test", actions=[action])

    # Act
    orchestrator._process_plan_actions(plan, interactive=False)

    # Assert
    executor.handle_skipped_action.assert_called_with(
        action, "User deselected this action in the plan reviewer."
    )
