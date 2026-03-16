import pytest
from teddy_executor.core.domain.models.execution_report import RunStatus
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator


@pytest.fixture
def orchestrator(container):
    """Provides a real ExecutionOrchestrator for integration testing."""
    container.register(IRunPlanUseCase, ExecutionOrchestrator)
    return container.resolve(IRunPlanUseCase)


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


def test_edit_action_is_dispatched_to_filesystem(container, mock_fs):
    """
    Given a Plan with an EDIT action,
    When the plan is executed,
    Then the ExecutionOrchestrator should dispatch the action to the IFileSystemManager.
    """
    # Arrange
    # Register this specific mock instance so the orchestrator and validator share it.
    container.register(IFileSystemManager, instance=mock_fs)
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "old"

    # Resolve orchestrator manually to pick up the instance registration.
    orchestrator = container.resolve(ExecutionOrchestrator)

    plan = Plan(
        title="Test Edit",
        rationale="Test Rationale",
        actions=[
            ActionData(
                type="EDIT",
                params={
                    "path": "code.py",
                    "edits": [{"find": "old", "replace": "new"}],
                },
            )
        ],
        metadata={
            "Agent": "Developer",
            "Plan Type": "Implementation",
            "Status": "Green 🟢",
        },
    )

    # Act
    report = orchestrator.execute(plan=plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    # We check that edit_file was called. The exact parameters may vary by
    # implementation (e.g., passing the list of edits).
    assert mock_fs.edit_file.called


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
    # We expect the default timeout (30.0) from config/config.yaml
    original_execute.assert_called_once_with(command="echo hello", timeout=30.0)


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
