from pytest_httpserver import HTTPServer

from tests.acceptance.helpers import (
    run_cli_with_markdown_plan_on_clipboard,
    parse_markdown_report,
)
from .plan_builder import MarkdownPlanBuilder


def test_read_action_can_read_from_url(httpserver: HTTPServer, monkeypatch, tmp_path):
    """
    Given a plan with a READ action targeting a URL,
    When the plan is executed,
    Then the action should succeed and the report should contain the scraped content.
    """
    # Arrange
    httpserver.expect_request("/testpage").respond_with_data(
        "<html><body><h1>Hello</h1><p>World</p></body></html>",
        content_type="text/html",
    )
    url = httpserver.url_for("/testpage")

    builder = MarkdownPlanBuilder("Test Read URL")
    builder.add_action(
        "READ",
        params={
            "Resource": f"[{url}]({url})",
            "Description": "Read content from a remote URL.",
        },
    )
    plan_content = builder.build()

    # Act
    result = run_cli_with_markdown_plan_on_clipboard(
        monkeypatch, plan_content, tmp_path
    )

    # Assert
    assert result.exit_code == 0, f"CLI exited with error: {result.stdout}"

    report = parse_markdown_report(result.stdout)

    assert "action_logs" in report
    assert len(report["action_logs"]) == 1
    read_action_log = report["action_logs"][0]

    assert read_action_log["status"] == "SUCCESS"

    # The contract for a successful read is the Resource Contents section in stdout
    assert "## Resource Contents" in result.stdout
    # markdownify uses Setext-style headers by default
    expected_content = "Hello\n=====\n\nWorld"
    assert expected_content in result.stdout
