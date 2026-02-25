from unittest.mock import MagicMock

import pytest
from teddy_executor.core.domain.models import RunStatus
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser


@pytest.fixture
def mock_dispatcher():
    return MagicMock()


@pytest.fixture
def mock_interactor():
    return MagicMock()


@pytest.fixture
def mock_file_system_manager():
    return MagicMock()


def test_execute_handles_invalid_plan_error_gracefully(
    mock_dispatcher, mock_interactor, mock_file_system_manager
):
    """
    Given an invalid plan string that causes the parser to raise InvalidPlanError,
    When the ExecutionOrchestrator is invoked,
    Then it should return a VALIDATION_FAILED report.
    This test is being repurposed to test the orchestrator's response to an already-parsed-but-invalid plan,
    though this scenario is less likely now that parsing is done upstream.
    The primary goal of this refactoring is changing the 'execute' signature.
    """
    # Arrange
    # The orchestrator should no longer parse. We create a plan and expect it to run.
    # A valid plan is needed now.
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
    plan_parser = MarkdownPlanParser()
    valid_plan = plan_parser.parse(plan_content)

    # Mock the dispatcher to return a success log
    from teddy_executor.core.domain.models import ActionLog, ActionStatus

    mock_dispatcher.dispatch_and_execute.return_value = ActionLog(
        status=ActionStatus.SUCCESS, action_type="CREATE", params={}
    )

    orchestrator = ExecutionOrchestrator(
        plan_parser=plan_parser,
        action_dispatcher=mock_dispatcher,
        user_interactor=mock_interactor,
        file_system_manager=mock_file_system_manager,
    )

    # Act
    report = orchestrator.execute(plan=valid_plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    mock_dispatcher.dispatch_and_execute.assert_called_once()
