from unittest.mock import MagicMock

# This import will fail
from teddy.core.services.plan_service import PlanService
from teddy.core.ports.outbound.shell_executor import ShellExecutor
from teddy.core.domain.models import (
    CommandResult,
    ExecuteAction,
    CreateFileAction,
    ParsePlanAction,
)
from teddy.core.ports.outbound.file_system_manager import FileSystemManager
from teddy.core.services.action_factory import ActionFactory


def test_plan_service_handles_invalid_yaml():
    """
    Tests that PlanService returns a failure report for malformed YAML.
    """
    # ARRANGE
    mock_shell_executor = MagicMock(spec=ShellExecutor)
    mock_file_system_manager = MagicMock(spec=FileSystemManager)
    mock_action_factory = MagicMock(spec=ActionFactory)

    # Configure the mock factory to return an object with the expected action_type
    mock_parse_action = ParsePlanAction()
    mock_action_factory.create_action.return_value = mock_parse_action

    plan_service = PlanService(
        shell_executor=mock_shell_executor,
        file_system_manager=mock_file_system_manager,
        action_factory=mock_action_factory,
    )
    invalid_plan_content = "this is not valid yaml: { oh no"

    # ACT
    report = plan_service.execute(invalid_plan_content)

    # ASSERT
    mock_shell_executor.run.assert_not_called()
    assert len(report.action_logs) == 1
    action_result = report.action_logs[0]
    assert action_result.status == "FAILURE"
    assert "Failed to process plan" in action_result.error
    assert action_result.action.action_type == "parse_plan"


def test_plan_service_populates_run_summary():
    """
    Tests that PlanService correctly populates the run_summary in the report.
    """
    # ARRANGE
    mock_shell_executor = MagicMock(spec=ShellExecutor)
    mock_file_system_manager = MagicMock(spec=FileSystemManager)
    mock_action_factory = MagicMock(spec=ActionFactory)
    # Simulate one success and one failure
    mock_shell_executor.run.side_effect = [
        CommandResult(stdout="ok", stderr="", return_code=0),
        CommandResult(stdout="", stderr="error", return_code=1),
    ]

    # Configure the mock factory to return objects the service can interact with
    mock_action_factory.create_action.side_effect = [
        ExecuteAction(command="true"),
        ExecuteAction(command="false"),
        ExecuteAction(command="true"),
    ]

    plan_service = PlanService(
        shell_executor=mock_shell_executor,
        file_system_manager=mock_file_system_manager,
        action_factory=mock_action_factory,
    )
    plan_content = """
    - { action: execute, params: { command: "true" } }
    - { action: execute, params: { command: "false" } }
    """

    # ACT
    report = plan_service.execute(plan_content)

    # ASSERT
    assert report.run_summary.get("status") == "FAILURE"

    # Test the SUCCESS case
    mock_shell_executor.run.side_effect = [
        CommandResult(stdout="ok", stderr="", return_code=0)
    ]
    plan_content_success = """
    - { action: execute, params: { command: "true" } }
    """
    report_success = plan_service.execute(plan_content_success)
    assert report_success.run_summary.get("status") == "SUCCESS"


def test_plan_service_parses_and_executes_plan():
    """
    Tests that PlanService can parse a valid YAML plan and call the shell executor.
    """
    # ARRANGE
    # 1. Mock the outbound port (ShellExecutor)
    mock_shell_executor = MagicMock(spec=ShellExecutor)
    mock_file_system_manager = MagicMock(spec=FileSystemManager)
    mock_action_factory = MagicMock(spec=ActionFactory)
    mock_shell_executor.run.return_value = CommandResult(
        stdout="hello world", stderr="", return_code=0
    )

    # Configure the mock factory to return a mock action object with the necessary attributes
    mock_action = ExecuteAction(command='echo "hello world"')
    mock_action_factory.create_action.return_value = mock_action

    # 2. Instantiate the service with the mock dependency
    plan_service = PlanService(
        shell_executor=mock_shell_executor,
        file_system_manager=mock_file_system_manager,
        action_factory=mock_action_factory,
    )

    # 3. Define the input YAML
    plan_content = """
    - action: execute
      params:
        command: echo "hello world"
    """

    # ACT
    report = plan_service.execute(plan_content)

    # ASSERT
    # 1. Assert the outbound port was called correctly
    mock_shell_executor.run.assert_called_once_with('echo "hello world"')

    # 2. Assert the report contains the correct information
    assert len(report.action_logs) == 1
    action_result = report.action_logs[0]
    assert action_result.status == "SUCCESS"
    assert action_result.output == "hello world"
    assert action_result.action.action_type == "execute"


def test_plan_service_handles_create_file_action():
    """
    Tests that PlanService can parse a create_file action and call the file system manager.
    """
    # ARRANGE
    mock_shell_executor = MagicMock(spec=ShellExecutor)
    mock_file_system_manager = MagicMock(spec=FileSystemManager)
    mock_action_factory = MagicMock(spec=ActionFactory)

    mock_action = CreateFileAction(
        file_path="foo/bar.txt",
        content="Hello from teddy!",
    )
    mock_action_factory.create_action.return_value = mock_action

    plan_service = PlanService(
        shell_executor=mock_shell_executor,
        file_system_manager=mock_file_system_manager,
        action_factory=mock_action_factory,
    )

    plan_content = """
    - action: create_file
      params:
        file_path: "foo/bar.txt"
        content: "Hello from teddy!"
    """

    # ACT
    report = plan_service.execute(plan_content)

    # ASSERT
    mock_file_system_manager.create_file.assert_called_once_with(
        path="foo/bar.txt", content="Hello from teddy!"
    )
    mock_shell_executor.run.assert_not_called()

    assert len(report.action_logs) == 1
    action_result = report.action_logs[0]
    assert action_result.status == "COMPLETED"
    assert action_result.action.action_type == "create_file"
    assert action_result.output == "Created file: foo/bar.txt"


def test_execute_create_file_handles_file_exists_error():
    """
    Given a create_file action for a file that already exists,
    When the plan is executed,
    Then the service should catch the FileExistsError and return a FAILURE ActionResult.
    """
    # Arrange
    mock_shell_executor = MagicMock(spec=ShellExecutor)
    mock_file_system_manager = MagicMock(spec=FileSystemManager)
    mock_action_factory = MagicMock(spec=ActionFactory)

    file_path = "/path/to/existing_file.txt"
    mock_action = CreateFileAction(file_path=file_path, content="")
    mock_action_factory.create_action.return_value = mock_action

    plan_service = PlanService(
        shell_executor=mock_shell_executor,
        file_system_manager=mock_file_system_manager,
        action_factory=mock_action_factory,
    )
    plan_content = f"""
    - action: create_file
      params:
        file_path: "{file_path}"
    """

    # Configure the mock to simulate the file already existing
    mock_exception = FileExistsError()
    mock_exception.strerror = "File exists"
    mock_exception.filename = file_path
    mock_file_system_manager.create_file.side_effect = mock_exception

    # Act
    report = plan_service.execute(plan_content)

    # Assert
    assert len(report.action_logs) == 1
    result = report.action_logs[0]
    assert result.status == "FAILURE"
    # The service should construct a user-friendly error message.
    expected_error_message = f"File exists: '{file_path}'"
    assert result.error == expected_error_message
    assert result.output is None

    # Verify the mock was called
    mock_file_system_manager.create_file.assert_called_once_with(
        path=file_path, content=""
    )
