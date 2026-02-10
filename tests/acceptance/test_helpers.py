from .helpers import parse_markdown_report


def test_parse_markdown_report_summary():
    """
    Given a markdown report string,
    When the report is parsed,
    Then the summary details should be correctly extracted.
    """
    report_md = """
# Execution Report
- **Overall Status:** Success 🟢
- **Actions:** 2 Total / 2 Approved / 0 Skipped
- **Outcomes:** 2 Succeeded / 0 Failed
"""

    parsed_report = parse_markdown_report(report_md)

    expected_summary = {
        "Overall Status": "Success 🟢",
        "Actions": "2 Total / 2 Approved / 0 Skipped",
        "Outcomes": "2 Succeeded / 0 Failed",
    }

    assert parsed_report["run_summary"] == expected_summary
