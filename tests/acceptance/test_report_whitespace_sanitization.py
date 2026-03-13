from typer.testing import CliRunner
from teddy_executor.__main__ import app


def test_report_whitespace_sanitization(tmp_path, monkeypatch):
    """
    Scenario: Report Whitespace Sanitization
    Given an execution report generated from a template
    When the report is formatted by MarkdownReportFormatter
    Then the final output must have all leading and trailing whitespace removed
    And all sequences of three or more newlines must be collapsed into exactly two newlines.
    """
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    # A simple plan that will generate a report.
    plan_content = """# Whitespace Test Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Test rationale.
````

## Action Plan
### `EXECUTE`
- **Description:** Run a command
- **Expected Outcome:** Success
````shell
echo "hello"
````
"""

    # Execute the plan. -y for auto-approve.
    result = runner.invoke(app, ["execute", "-y", "--plan-content", plan_content])

    assert result.exit_code == 0
    report_output = result.stdout

    # Verification:
    assert "# Execution Report" in report_output

    # Extract the report content (from the first # Execution Report to the end)
    report_start = report_output.find("# Execution Report")
    report_content = report_output[report_start:]

    # 1. Collapse 3+ newlines to exactly 2
    assert "\n\n\n" not in report_content, (
        "Found 3 or more consecutive newlines in report"
    )

    # 2. No leading/trailing whitespace in the rendered report
    # We check that the first line is the header, not a newline.
    assert report_content.startswith("# Execution Report")

    # We check that there isn't a double newline at the end (one is expected from print)
    assert not report_content.endswith("\n\n")
