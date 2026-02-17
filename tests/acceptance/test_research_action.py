from pathlib import Path
from unittest.mock import MagicMock, patch


from teddy_executor.core.domain.models._legacy_models import (
    QueryResult,
    SearchResult,
    SERPReport,
)
from teddy_executor.core.ports.outbound import IWebSearcher
from teddy_executor.main import create_container

from .helpers import parse_markdown_report, run_cli_with_markdown_plan_on_clipboard
from .plan_builder import MarkdownPlanBuilder


def test_research_action_success(monkeypatch, tmp_path: Path):
    """
    Given a plan with a `research` action,
    When the plan is executed with a mocked web searcher,
    Then it should return a report with the mocked search results.
    """
    # Arrange
    builder = MarkdownPlanBuilder("Test Research Action")
    builder.add_action(
        "RESEARCH",
        params={"Description": "Research python typer."},
        content_blocks={"QUERY": ("text", "python typer")},
    )
    plan_content = builder.build()

    mock_web_searcher = MagicMock(spec=IWebSearcher)
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

    test_container = create_container()
    test_container.register(IWebSearcher, instance=mock_web_searcher)

    # Act
    with patch("teddy_executor.main.container", test_container):
        result = run_cli_with_markdown_plan_on_clipboard(
            monkeypatch, plan_content, tmp_path
        )

    # Assert
    assert result.exit_code == 0
    mock_web_searcher.search.assert_called_once_with(queries=["python typer"])

    # Verify structured output
    assert "### `RESEARCH`: Research python typer." in result.stdout
    assert "**Query:** `python typer`" in result.stdout
    # Expect link format: [Title](URL)
    assert "[Typer Tutorial](https://typer.tiangolo.com/)" in result.stdout
    # Expect unindented Snippet block
    assert "```Snippet" in result.stdout
    assert "A great tutorial for Typer." in result.stdout

    report = parse_markdown_report(result.stdout)
    assert report["run_summary"]["Overall Status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"

    # Note: Raw details are no longer rendered for RESEARCH actions in the concise report.
    # We verify the content via the structured output checks above.
