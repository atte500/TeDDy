import pytest
from teddy_executor.core.domain.models import ActionLog, ActionStatus, RunStatus
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator


@pytest.fixture
def orchestrator(
    container,
    mock_action_dispatcher,
    mock_user_interactor,
    mock_fs,
):
    from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser

    container.register(IPlanParser, MarkdownPlanParser)
    container.register(IRunPlanUseCase, ExecutionOrchestrator)
    return container.resolve(IRunPlanUseCase)


def test_execute_handles_valid_plan_successfully(
    container, orchestrator, mock_action_dispatcher
):
    """
    Given a valid plan,
    When the ExecutionOrchestrator is invoked,
    Then it should return a SUCCESS report.
    """
    # Arrange
    plan_parser = container.resolve(IPlanParser)

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
    mock_action_dispatcher.dispatch_and_execute.return_value = ActionLog(
        status=ActionStatus.SUCCESS, action_type="CREATE", params={}
    )

    # Act
    report = orchestrator.execute(plan=valid_plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    mock_action_dispatcher.dispatch_and_execute.assert_called_once()
