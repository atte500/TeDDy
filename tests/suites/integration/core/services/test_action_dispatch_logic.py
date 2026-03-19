from teddy_executor.core.domain.models.execution_report import RunStatus
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from tests.harness.setup.test_environment import TestEnvironment


def test_create_action_is_dispatched_to_filesystem(monkeypatch):
    """
    Given a Plan with a CREATE action,
    When the plan is executed,
    Then it should dispatch the action to the IFileSystemManager.
    """
    # Arrange
    env = TestEnvironment(monkeypatch).setup()
    orchestrator = env.get_service(IRunPlanUseCase)
    mock_fs = env.get_mock_filesystem()

    plan = Plan(
        title="Test Plan",
        rationale="Test Rationale",
        actions=[
            ActionData(type="CREATE", params={"path": "hello.txt", "content": "Hello!"})
        ],
    )

    # Act
    report = orchestrator.execute(plan=plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    mock_fs.create_file.assert_called_once_with(path="hello.txt", content="Hello!")


def test_edit_action_is_dispatched_to_filesystem(monkeypatch):
    """
    Given a Plan with an EDIT action,
    When the plan is executed,
    Then it should dispatch the action to the IFileSystemManager.
    """
    # Arrange
    env = TestEnvironment(monkeypatch).setup()
    orchestrator = env.get_service(IRunPlanUseCase)
    mock_fs = env.get_mock_filesystem()

    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "old"

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
    )

    # Act
    report = orchestrator.execute(plan=plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    assert mock_fs.edit_file.called


def test_execute_action_is_dispatched_to_shell(monkeypatch):
    """
    Given a Plan with an EXECUTE action,
    When the plan is executed,
    Then it should dispatch the action to the IShellExecutor.
    """
    # Arrange
    env = TestEnvironment(monkeypatch).setup()
    orchestrator = env.get_service(IRunPlanUseCase)
    mock_shell = env.get_mock_shell()

    # Capture the original mock method before it is wrapped/replaced by the service layer
    mock_execute = mock_shell.execute
    mock_execute.return_value = {"stdout": "hello", "return_code": 0}

    plan = Plan(
        title="Test Execute",
        rationale="Test Rationale",
        actions=[ActionData(type="EXECUTE", params={"command": "echo hello"})],
    )

    # Act
    report = orchestrator.execute(plan=plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    # We expect the default timeout (30.0)
    mock_execute.assert_called_once_with(command="echo hello", timeout=30.0)


def test_read_action_is_dispatched_to_filesystem(monkeypatch):
    """
    Given a Plan with a READ action,
    When the plan is executed,
    Then it should dispatch the action to the IFileSystemManager.
    """
    # Arrange
    env = TestEnvironment(monkeypatch).setup()
    orchestrator = env.get_service(IRunPlanUseCase)
    mock_fs = env.get_mock_filesystem()
    mock_fs.read_file.return_value = "content"

    plan = Plan(
        title="Test Read",
        rationale="Test Rationale",
        actions=[ActionData(type="READ", params={"path": "hello.txt"})],
    )

    # Act
    report = orchestrator.execute(plan=plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
    mock_fs.read_file.assert_called_once_with(path="hello.txt")


def test_invoke_action_returns_success(monkeypatch):
    """
    Given a Plan with an INVOKE action,
    When the plan is executed,
    Then it should return a SUCCESS report.
    """
    # Arrange
    env = TestEnvironment(monkeypatch).setup()
    orchestrator = env.get_service(IRunPlanUseCase)
    mock_user = env.get_mock_user_interactor()
    mock_user.confirm_manual_handoff.return_value = (True, "")

    plan = Plan(
        title="Test Invoke",
        rationale="Test Rationale",
        actions=[ActionData(type="INVOKE", params={"agent": "Architect"})],
    )

    # Act
    report = orchestrator.execute(plan=plan, interactive=False)

    # Assert
    assert report.run_summary.status == RunStatus.SUCCESS
