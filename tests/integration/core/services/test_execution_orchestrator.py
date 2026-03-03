from unittest.mock import MagicMock, Mock

import pytest
from teddy_executor.core.domain.models import ActionLog, ActionStatus, RunStatus
from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.run_plan_use_case import RunPlanUseCase
from teddy_executor.core.ports.outbound import IFileSystemManager, IUserInteractor
from teddy_executor.core.services.action_dispatcher import ActionDispatcher
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator


@pytest.fixture
def mocks(container):
    mock_dispatcher = MagicMock(spec=ActionDispatcher)
    mock_interactor = MagicMock(spec=IUserInteractor)
    mock_file_system_manager = MagicMock(spec=IFileSystemManager)
    mock_edit_simulator = Mock(spec=IEditSimulator)

    from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser

    container.register(IPlanParser, MarkdownPlanParser)
    container.register(ActionDispatcher, instance=mock_dispatcher)
    container.register(IUserInteractor, instance=mock_interactor)
    container.register(IFileSystemManager, instance=mock_file_system_manager)
    container.register(IEditSimulator, instance=mock_edit_simulator)
    container.register(RunPlanUseCase, ExecutionOrchestrator)

    return {
        "dispatcher": mock_dispatcher,
        "interactor": mock_interactor,
        "file_system_manager": mock_file_system_manager,
    }


def test_execute_handles_valid_plan_successfully(container, mocks):
    """
    Given a valid plan,
    When the ExecutionOrchestrator is invoked,
    Then it should return a SUCCESS report.
    """
    # Arrange
    plan_parser = container.resolve(IPlanParser)
    orchestrator = container.resolve(RunPlanUseCase)
    mock_dispatcher = mocks["dispatcher"]

    plan_content = """
# Valid Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan
### `CREATE`
- **File Path:** [file1.txt](/file1.txt)
- **Description:** First file.
````text
content1
````
"""
    valid_plan = plan_parser.parse(plan_content)

    # Mock the dispatcher to return a success log
    mock_dispatcher.dispatch_and_execute.return_value = ActionLog(
        status=ActionStatus.SUCCESS, action_type="CREATE", params={}
    )

    # Act
    report = orchestrator.execute(plan=valid_plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    mock_dispatcher.dispatch_and_execute.assert_called_once()
