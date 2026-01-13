import json
from unittest.mock import MagicMock

# Import core components to build the service manually
from teddy_executor.core.services.plan_service import PlanService
from teddy_executor.core.services.action_factory import ActionFactory
from teddy_executor.core.domain.models import SERPReport, QueryResult, SearchResult


def test_research_action_success():
    """
    Scenario: Successful Web Search (run in-process)
    Given a plan with a `research` action,
    When the PlanService executes the plan,
    Then it calls the WebSearcher and returns a report with the results.
    """
    # Arrange
    plan_text = """
- action: research
  params:
    queries: |
      python typer
    """

    # 1. Create mocks for all of PlanService's dependencies
    mock_shell_executor = MagicMock()
    mock_file_system_manager = MagicMock()
    mock_web_scraper = MagicMock()
    mock_user_interactor = MagicMock()
    # Add default approval to prevent interactive mode from breaking the test
    mock_user_interactor.confirm_action.return_value = (True, "")
    mock_web_searcher = MagicMock()

    # 2. Configure the mock_web_searcher to return a predictable domain object
    serp_report = SERPReport(
        results=[
            QueryResult(
                query="python typer",
                search_results=[
                    SearchResult(
                        title="Typer Tutorial",
                        url="https://typer.tiangolo.com/",
                        snippet="A great tutorial for Typer.",
                    )
                ],
            )
        ]
    )
    mock_web_searcher.search.return_value = serp_report

    # 3. Instantiate the real ActionFactory and the PlanService with mocks
    action_factory = ActionFactory()
    plan_service = PlanService(
        shell_executor=mock_shell_executor,
        file_system_manager=mock_file_system_manager,
        action_factory=action_factory,
        web_scraper=mock_web_scraper,
        user_interactor=mock_user_interactor,
        web_searcher=mock_web_searcher,
    )

    # Act
    report = plan_service.execute(plan_text)

    # Assert
    assert report.run_summary["status"] == "SUCCESS"

    # Verify the web searcher was called correctly
    mock_web_searcher.search.assert_called_once_with(queries=["python typer"])

    # Verify the action log in the report
    action_logs = report.action_logs
    assert len(action_logs) == 1
    research_log = action_logs[0]
    assert research_log.status == "SUCCESS"
    assert research_log.error is None

    # Verify the JSON output in the report
    output_data = json.loads(research_log.output)
    assert len(output_data["results"]) == 1
    first_result_set = output_data["results"][0]
    assert first_result_set["query"] == "python typer"
    assert len(first_result_set["search_results"]) == 1
    first_search_result = first_result_set["search_results"][0]
    assert first_search_result["title"] == "Typer Tutorial"
