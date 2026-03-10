import pytest
import textwrap
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


def test_orchestrator_skips_terminal_action_in_multi_action_plan_integration(
    orchestrator, mock_action_dispatcher
):
    """
    Scenario: Orchestrator skips terminal actions when part of a multi-action plan.
    """
    plan_content = textwrap.dedent("""
        # Integration Test Isolation
        - Status: Green 🟢
        - Plan Type: Implementation
        - Agent: Developer

        ## Rationale
        ```text
        Testing isolation in integration.
        ```

        ## Action Plan

        ### `EXECUTE`
        - **Description:** Listing files.
        ````shell
        ls
        ````

        ### `PROMPT`
        Please confirm this prompt.
    """).strip()

    # Mock the dispatcher to return success for EXECUTE
    mock_action_dispatcher.dispatch_and_execute.return_value = ActionLog(
        status=ActionStatus.SUCCESS, action_type="EXECUTE", params={}
    )

    report = orchestrator.execute(plan_content=plan_content, interactive=False)

    expected_count = 2
    assert len(report.action_logs) == expected_count
    # First action (EXECUTE) should succeed
    assert report.action_logs[0].action_type == "EXECUTE"
    assert report.action_logs[0].status == ActionStatus.SUCCESS
    # Second action (PROMPT) should be SKIPPED
    assert report.action_logs[1].action_type == "PROMPT"
    assert report.action_logs[1].status == ActionStatus.SKIPPED
    assert "Action must be executed in isolation" in report.action_logs[1].details


def test_orchestrator_skips_invoke_in_multi_action_plan_integration(
    orchestrator, mock_action_dispatcher
):
    """
    Scenario: Orchestrator skips INVOKE actions when part of a multi-action plan.
    """
    plan_content = textwrap.dedent("""
        # Integration Test INVOKE Isolation
        - Status: Green 🟢
        - Plan Type: Implementation
        - Agent: Developer

        ## Rationale
        ```text
        Testing INVOKE isolation in integration.
        ```

        ## Action Plan

        ### `EXECUTE`
        - **Description:** Listing files.
        ````shell
        ls
        ````

        ### `INVOKE`
        - **Agent:** Architect
        - **Description:** Moving to design phase.
    """).strip()

    # Mock the dispatcher to return success for EXECUTE
    mock_action_dispatcher.dispatch_and_execute.return_value = ActionLog(
        status=ActionStatus.SUCCESS, action_type="EXECUTE", params={}
    )

    report = orchestrator.execute(plan_content=plan_content, interactive=False)

    expected_count = 2
    assert len(report.action_logs) == expected_count
    # First action (EXECUTE) should succeed
    assert report.action_logs[0].action_type == "EXECUTE"
    assert report.action_logs[0].status == ActionStatus.SUCCESS
    # Second action (INVOKE) should be SKIPPED
    assert report.action_logs[1].action_type == "INVOKE"
    assert report.action_logs[1].status == ActionStatus.SKIPPED
    assert "Action must be executed in isolation" in report.action_logs[1].details
