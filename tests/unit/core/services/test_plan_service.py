import json
from unittest.mock import MagicMock
from teddy.core.domain.models import (
    ChatWithUserAction,
    CommandResult,
    CreateFileAction,
    ExecuteAction,
    ParsePlanAction,
    ReadAction,
    EditAction,
    ResearchAction,
    SERPReport,
    QueryResult,
    SearchResult,
    MultipleMatchesFoundError,
)
from teddy.core.services.plan_service import PlanService


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


def test_execute_create_file_handles_file_already_exists_error(
    plan_service, mock_file_system_manager, mock_action_factory
):
    """
    Tests that when create_file fails because a file exists, it reads
    the file's content and includes it in the action result.
    """
    from teddy.core.domain.models import FileAlreadyExistsError

    # Arrange
    file_path = "/path/to/existing_file.txt"
    original_content = "This is the original content."
    mock_action = CreateFileAction(file_path=file_path, content="new content")
    mock_action_factory.create_action.return_value = mock_action

    # Configure mocks
    mock_file_system_manager.create_file.side_effect = FileAlreadyExistsError(
        message="File already exists", file_path=file_path
    )
    mock_file_system_manager.read_file.return_value = original_content
    plan_content = f"""
    - action: create_file
      params:
        file_path: "{file_path}"
        content: "new content"
    """

    # Act
    report = plan_service.execute(plan_content)

    # Assert
    # Check that it tried to create the file
    mock_file_system_manager.create_file.assert_called_once()
    # Check that it then tried to read the file
    mock_file_system_manager.read_file.assert_called_once_with(path=file_path)

    result = report.action_logs[0]
    assert result.status == "FAILURE"
    assert "File already exists" in result.error
    assert result.output == original_content


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


def test_plan_service_handles_edit_action(
    plan_service, mock_file_system_manager, mock_action_factory
):
    """
    Tests that PlanService can parse an edit action and call the file system manager.
    """
    # ARRANGE
    mock_action = EditAction(file_path="foo/bar.txt", find="old", replace="new")
    mock_action_factory.create_action.return_value = mock_action
    plan_content = """
    - action: edit
      params:
        file_path: "foo/bar.txt"
        find: "old"
        replace: "new"
    """

    # ACT
    plan_service.execute(plan_content)

    # ASSERT
    mock_file_system_manager.edit_file.assert_called_once_with(
        path="foo/bar.txt", find="old", replace="new"
    )


def test_handle_edit_action_raises_multiple_matches_found_error(
    plan_service, mock_file_system_manager, mock_action_factory
):
    """
    Tests that PlanService returns a FAILURE when the edit action finds
    multiple matches for the `find` text.
    """
    # Arrange
    file_path = "path/to/file.txt"
    original_content = "hello world, hello again"
    mock_action = EditAction(file_path=file_path, find="hello", replace="goodbye")
    mock_action_factory.create_action.return_value = mock_action

    error_message = f"Multiple matches found for 'hello' in '{file_path}'"
    mock_file_system_manager.edit_file.side_effect = MultipleMatchesFoundError(
        message=error_message, content=original_content
    )
    plan_content = f"""
    - action: edit
      params:
        file_path: "{file_path}"
        find: "hello"
        replace: "goodbye"
    """

    # Act
    report = plan_service.execute(plan_content)

    # Assert
    result = report.action_logs[0]
    assert result.status == "FAILURE"
    assert result.error == error_message
    assert result.output == original_content


def test_plan_service_handles_chat_with_user_action():
    """
    Tests that PlanService calls the UserInteractor port for a chat action.
    """
    # ARRANGE
    # Manually instantiate PlanService with a mock for the new port
    mock_shell_executor = MagicMock()
    mock_file_system_manager = MagicMock()
    mock_action_factory = MagicMock()
    mock_web_scraper = MagicMock()
    mock_user_interactor = MagicMock()
    mock_web_searcher = MagicMock()  # Add the new mock

    plan_service = PlanService(
        shell_executor=mock_shell_executor,
        file_system_manager=mock_file_system_manager,
        action_factory=mock_action_factory,
        web_scraper=mock_web_scraper,
        user_interactor=mock_user_interactor,
        web_searcher=mock_web_searcher,  # Pass the new mock
    )

    prompt_text = "What is your quest?"
    user_response = "To seek the Holy Grail."

    mock_action = ChatWithUserAction(prompt=prompt_text)
    mock_action_factory.create_action.return_value = mock_action
    mock_user_interactor.ask_question.return_value = user_response

    plan_content = f"""
    - action: chat_with_user
      params:
        prompt: "{prompt_text}"
    """

    # ACT
    report = plan_service.execute(plan_content)

    # ASSERT
    mock_user_interactor.ask_question.assert_called_once_with(prompt=prompt_text)
    action_result = report.action_logs[0]
    assert action_result.status == "SUCCESS"
    assert action_result.output == user_response


def test_plan_service_handles_research_action_success():
    """
    Tests that PlanService calls the WebSearcher port for a research action
    and correctly serializes the SERPReport to JSON.
    """
    # ARRANGE
    mock_shell_executor = MagicMock()
    mock_file_system_manager = MagicMock()
    mock_action_factory = MagicMock()
    mock_web_scraper = MagicMock()
    mock_user_interactor = MagicMock()
    mock_web_searcher = MagicMock()

    plan_service = PlanService(
        shell_executor=mock_shell_executor,
        file_system_manager=mock_file_system_manager,
        action_factory=mock_action_factory,
        web_scraper=mock_web_scraper,
        user_interactor=mock_user_interactor,
        web_searcher=mock_web_searcher,
    )

    queries = ["python web scraping", "beautiful soup tutorial"]
    mock_action = ResearchAction(queries=queries)
    mock_action_factory.create_action.return_value = mock_action

    # This is the object the port is expected to return
    serp_report = SERPReport(
        results=[
            QueryResult(
                query="python web scraping",
                search_results=[
                    SearchResult(
                        title="Web Scraping with Python",
                        url="https://example.com/scrape",
                        snippet="A guide to web scraping.",
                    )
                ],
            )
        ]
    )
    mock_web_searcher.search.return_value = serp_report

    plan_content = """
    - action: research
      params:
        queries:
          - python web scraping
          - beautiful soup tutorial
    """

    # ACT
    report = plan_service.execute(plan_content)

    # ASSERT
    mock_web_searcher.search.assert_called_once_with(queries=queries)
    action_result = report.action_logs[0]
    assert action_result.status == "SUCCESS"

    # Verify the output is a correctly structured JSON string
    output_data = json.loads(action_result.output)
    assert output_data["results"][0]["query"] == "python web scraping"
    assert (
        output_data["results"][0]["search_results"][0]["title"]
        == "Web Scraping with Python"
    )
