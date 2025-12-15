from teddy.core.domain.models import (
    CommandResult,
    CreateFileAction,
    ExecuteAction,
    ParsePlanAction,
    ReadAction,
)


def test_plan_service_handles_invalid_yaml(
    plan_service, mock_action_factory, mock_shell_executor
):
    """
    Tests that PlanService returns a failure report for malformed YAML.
    """
    # ARRANGE

    mock_parse_action = ParsePlanAction()
    mock_action_factory.create_action.return_value = mock_parse_action
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


def test_plan_service_populates_run_summary(
    plan_service, mock_shell_executor, mock_action_factory
):
    """
    Tests that PlanService correctly populates the run_summary in the report.
    """
    # ARRANGE

    # Simulate one success and one failure
    mock_shell_executor.run.side_effect = [
        CommandResult(stdout="ok", stderr="", return_code=0),
        CommandResult(stdout="", stderr="error", return_code=1),
    ]
    mock_action_factory.create_action.side_effect = [
        ExecuteAction(command="true"),
        ExecuteAction(command="false"),
    ]
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
    mock_action_factory.create_action.side_effect = [ExecuteAction(command="true")]
    plan_content_success = """
    - { action: execute, params: { command: "true" } }
    """
    report_success = plan_service.execute(plan_content_success)
    assert report_success.run_summary.get("status") == "SUCCESS"


def test_plan_service_parses_and_executes_plan(
    plan_service, mock_shell_executor, mock_action_factory
):
    """
    Tests that PlanService can parse a valid YAML plan and call the shell executor.
    """
    # ARRANGE

    mock_shell_executor.run.return_value = CommandResult(
        stdout="hello world", stderr="", return_code=0
    )
    mock_action = ExecuteAction(command='echo "hello world"')
    mock_action_factory.create_action.return_value = mock_action
    plan_content = """
    - action: execute
      params:
        command: echo "hello world"
    """

    # ACT
    report = plan_service.execute(plan_content)

    # ASSERT
    mock_shell_executor.run.assert_called_once_with('echo "hello world"')
    assert len(report.action_logs) == 1
    action_result = report.action_logs[0]
    assert action_result.status == "SUCCESS"
    assert action_result.output == "hello world"
    assert action_result.action.action_type == "execute"


def test_plan_service_handles_create_file_action(
    plan_service, mock_file_system_manager, mock_shell_executor, mock_action_factory
):
    """
    Tests that PlanService can parse a create_file action and call the file system manager.
    """
    # ARRANGE

    mock_action = CreateFileAction(file_path="foo/bar.txt", content="Hello!")
    mock_action_factory.create_action.return_value = mock_action
    plan_content = """
    - action: create_file
      params:
        file_path: "foo/bar.txt"
        content: "Hello!"
    """

    # ACT
    report = plan_service.execute(plan_content)

    # ASSERT
    mock_file_system_manager.create_file.assert_called_once_with(
        path="foo/bar.txt", content="Hello!"
    )
    mock_shell_executor.run.assert_not_called()
    action_result = report.action_logs[0]
    assert action_result.status == "COMPLETED"


def test_execute_create_file_handles_file_exists_error(
    plan_service, mock_file_system_manager, mock_action_factory
):
    """
    Tests handling of FileExistsError during file creation.
    """
    # Arrange

    file_path = "/path/to/existing_file.txt"
    mock_action = CreateFileAction(file_path=file_path, content="")
    mock_action_factory.create_action.return_value = mock_action

    mock_exception = FileExistsError()
    mock_exception.strerror = "File exists"
    mock_exception.filename = file_path
    mock_file_system_manager.create_file.side_effect = mock_exception
    plan_content = f"""
    - action: create_file
      params:
        file_path: "{file_path}"
        content: ""
    """

    # Act
    report = plan_service.execute(plan_content)

    # Assert
    result = report.action_logs[0]
    assert result.status == "FAILURE"
    assert result.error == f"File exists: '{file_path}'"


def test_plan_service_handles_read_file_action(
    plan_service, mock_file_system_manager, mock_action_factory
):
    """
    Tests that PlanService can parse a read action and call the file system manager.
    """
    # ARRANGE

    source_path = "path/to/some/file.txt"
    expected_content = "some file content"
    mock_action = ReadAction(source=source_path)
    mock_action_factory.create_action.return_value = mock_action
    mock_file_system_manager.read_file.return_value = expected_content
    plan_content = f"""
    - action: read
      params:
        source: "{source_path}"
    """

    # ACT
    report = plan_service.execute(plan_content)

    # ASSERT
    mock_file_system_manager.read_file.assert_called_once_with(path=source_path)
    action_result = report.action_logs[0]
    assert action_result.status == "SUCCESS"
    assert action_result.output == expected_content


def test_plan_service_handles_read_file_not_found_error(
    plan_service, mock_file_system_manager, mock_action_factory
):
    """
    Tests handling of FileNotFoundError during file reading.
    """
    # Arrange

    file_path = "path/to/non_existent_file.txt"
    mock_action = ReadAction(source=file_path)
    mock_action_factory.create_action.return_value = mock_action

    error_message = f"No such file or directory: '{file_path}'"
    mock_file_system_manager.read_file.side_effect = FileNotFoundError(error_message)
    plan_content = f"""
    - action: read
      params:
        source: "{file_path}"
    """

    # Act
    report = plan_service.execute(plan_content)

    # Assert
    result = report.action_logs[0]
    assert result.status == "FAILURE"
    assert result.error == error_message


def test_plan_service_handles_read_url_action(
    plan_service, mock_web_scraper, mock_file_system_manager, mock_action_factory
):
    """
    Tests that PlanService calls the WebScraper port when the source is a URL.
    """
    # ARRANGE

    source_url = "https://example.com/page"
    expected_content = "web page content"
    mock_action = ReadAction(source=source_url)
    mock_action_factory.create_action.return_value = mock_action
    mock_web_scraper.get_content.return_value = expected_content
    plan_content = f"""
    - action: read
      params:
        source: "{source_url}"
    """

    # ACT
    report = plan_service.execute(plan_content)

    # ASSERT
    mock_web_scraper.get_content.assert_called_once_with(url=source_url)
    mock_file_system_manager.read_file.assert_not_called()
    action_result = report.action_logs[0]
    assert action_result.status == "SUCCESS"
    assert action_result.output == expected_content
