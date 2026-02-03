from pathlib import Path
from unittest.mock import MagicMock, patch
import yaml
from typer.testing import CliRunner

from teddy_executor.main import app, create_container
from .helpers import parse_yaml_report
from teddy_executor.core.ports.outbound import IWebSearcher
from teddy_executor.core.domain.models._legacy_models import (
    SERPReport,
    QueryResult,
    SearchResult,
)


def test_research_action_success(tmp_path: Path):
    """
    Given a plan with a `research` action,
    When the plan is executed with a mocked web searcher,
    Then it should return a report with the mocked search results.
    """
    # Arrange
    runner = CliRunner()
    plan_structure = [
        {
            "action": "research",
            "params": {"queries": ["python typer"]},
        }
    ]
    plan_content = yaml.dump(plan_structure)
    plan_file = tmp_path / "plan.yml"
    plan_file.write_text(plan_content)

    # 1. Create a mock for the IWebSearcher port
    mock_web_searcher = MagicMock(spec=IWebSearcher)

    # 2. Configure the mock to return a predictable domain object
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

    # 3. Create a test-specific DI container and register the mock
    test_container = create_container()
    test_container.register(IWebSearcher, instance=mock_web_searcher)

    # Act
    with patch("teddy_executor.main.container", test_container):
        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

    # Assert
    assert result.exit_code == 0
    mock_web_searcher.search.assert_called_once_with(queries=["python typer"])

    report = parse_yaml_report(result.stdout)
    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"

    # The details should be the JSON representation of the SERPReport
    details_dict = action_log["details"]
    assert details_dict["results"][0]["query"] == "python typer"
    assert details_dict["results"][0]["search_results"][0]["title"] == "Typer Tutorial"
