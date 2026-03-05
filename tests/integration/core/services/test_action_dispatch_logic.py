import pytest
from teddy_executor.core.domain.models.execution_report import RunStatus
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.run_plan_use_case import RunPlanUseCase
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator


@pytest.fixture
def orchestrator(container):
    """Provides a real ExecutionOrchestrator for integration testing."""
    container.register(RunPlanUseCase, ExecutionOrchestrator)
    return container.resolve(RunPlanUseCase)


def test_create_action_is_dispatched_to_filesystem(orchestrator, mock_fs):
    """
    Given a Plan with a CREATE action,
    When the plan is executed,
    Then the ExecutionOrchestrator should dispatch the action to the IFileSystemManager.
    """
    # Arrange
    plan = Plan(
        title="Test Plan",
        rationale="Test Rationale",
        actions=[
            ActionData(
                type="CREATE",
                params={"path": "hello.txt", "content": "Hello, world!"},
            )
        ],
    )

    # Act
    report = orchestrator.execute(plan=plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    mock_fs.create_file.assert_called_once_with(
        path="hello.txt", content="Hello, world!"
    )


def test_edit_action_is_dispatched_to_filesystem(orchestrator, mock_fs):
    """
    Given a Plan with an EDIT action,
    When the plan is executed,
    Then the ExecutionOrchestrator should dispatch the action to the IFileSystemManager.
    """
    # Arrange
    plan = Plan(
        title="Test Edit",
        rationale="Test Rationale",
        actions=[
            ActionData(
                type="EDIT",
                params={"path": "code.py", "find": "old", "replace": "new"},
            )
        ],
    )

    # Act
    report = orchestrator.execute(plan=plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    mock_fs.edit_file.assert_called_once_with(path="code.py", find="old", replace="new")


def test_execute_action_is_dispatched_to_shell(container, orchestrator, mock_shell):
    """
    Given a Plan with an EXECUTE action,
    When the plan is executed,
    Then the ExecutionOrchestrator should dispatch the action to the IShellExecutor.
    """
    # Arrange
    plan = Plan(
        title="Test Execute",
        rationale="Test Rationale",
        actions=[
            ActionData(
                type="EXECUTE",
                params={"command": "echo hello"},
            )
        ],
    )
    # ActionFactory wraps the mock's method, replacing the attribute on the instance.
    # We capture the original mock method to assert on it later.
    original_execute = mock_shell.execute
    original_execute.return_value = {"stdout": "hello", "return_code": 0}

    # Act
    report = orchestrator.execute(plan=plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    original_execute.assert_called_once_with(command="echo hello")


def test_read_action_is_dispatched_to_filesystem(orchestrator, mock_fs):
    """
    Given a Plan with a READ action,
    When the plan is executed,
    Then the ExecutionOrchestrator should dispatch the action to the IFileSystemManager.
    """
    # Arrange
    plan = Plan(
        title="Test Read",
        rationale="Test Rationale",
        actions=[
            ActionData(
                type="READ",
                params={"path": "hello.txt"},
            )
        ],
    )
    mock_fs.read_file.return_value = "content"

    # Act
    report = orchestrator.execute(plan=plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    mock_fs.read_file.assert_called_once_with(path="hello.txt")


def test_invoke_action_returns_success(mock_user_interactor, orchestrator):
    """
    Given a Plan with an INVOKE action,
    When the plan is executed,
    Then it should return a SUCCESS report.
    """
    # Arrange
    plan = Plan(
        title="Test Invoke",
        rationale="Test Rationale",
        actions=[
            ActionData(
                type="INVOKE",
                params={"agent": "Architect"},
            )
        ],
    )
    # Mock the interactor to approve the handoff
    mock_user_interactor.confirm_manual_handoff.return_value = (True, "")

    # Act
    report = orchestrator.execute(plan=plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
