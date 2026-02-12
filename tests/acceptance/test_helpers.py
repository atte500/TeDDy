from .helpers import parse_markdown_report


def test_parse_markdown_report_with_params_and_details():
    """
    Given a markdown report string that matches the Jinja2 template format,
    When `parse_markdown_report` is called,
    Then it should correctly parse the nested Params list and the Details string.
    """
    report_md = """
# Execution Report: Test Plan

- **Overall Status:** SUCCESS
- **Execution Start Time:** 2024-01-01T12:00:00
- **Execution End Time:** 2024-01-01T12:00:01

## Execution Summary

### Action Log

#### `EXECUTE`
- **Status:** SUCCESS
- **Params:**
  - **command:** `echo "hello"`
  - **cwd:** `/tmp`
- **Details:** `{'stdout': 'hello', 'stderr': '', 'return_code': 0}`
"""
    parsed = parse_markdown_report(report_md)
    assert len(parsed["action_logs"]) == 1
    action_log = parsed["action_logs"][0]

    assert "params" in action_log
    assert action_log["params"] == {"command": 'echo "hello"', "cwd": "/tmp"}

    assert "details" in action_log
    assert action_log["details"] == {"stdout": "hello", "stderr": "", "return_code": 0}


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
