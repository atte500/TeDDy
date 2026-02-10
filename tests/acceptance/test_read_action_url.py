from typer.testing import CliRunner
from pytest_httpserver import HTTPServer

from teddy_executor.main import app
from tests.acceptance.helpers import create_plan_file

runner = CliRunner()


def test_read_action_can_read_from_url(httpserver: HTTPServer):
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

    plan_content = f"""
# Read from a URL
- **Goal:** Verify URL reading capability.

## Action Plan

### `READ`
- **Resource:** [{url}]({url})
- **Description:** Read content from a remote URL.
"""
    with create_plan_file(plan_content, ".md") as plan_path:
        # Act
        result = runner.invoke(
            app,
            ["execute", str(plan_path), "--no-copy", "-y"],
            catch_exceptions=False,
        )

    # Assert
    assert result.exit_code == 0, f"CLI exited with error: {result.stdout}"
    from tests.acceptance.helpers import parse_yaml_report

    report = parse_yaml_report(result.stdout)

    assert "action_logs" in report
    assert len(report["action_logs"]) == 1
    read_action_log = report["action_logs"][0]

    assert read_action_log["status"] == "SUCCESS"
    assert "details" in read_action_log
    assert "content" in read_action_log["details"]
    # markdownify uses Setext-style headers by default
    expected_content = "Hello\n=====\n\nWorld"
    assert read_action_log["details"]["content"].strip() == expected_content
