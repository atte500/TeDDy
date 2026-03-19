from textwrap import dedent
from tests.harness.observers.report_parser import ReportParser


def test_parse_exhaustive_report():
    """
    Verifies that the ReportParser can extract summary data and multiple action logs.
    """
    report_content = dedent("""\
        # Execution Report: Test Plan
        - **Overall Status:** SUCCESS
        - **Execution Start Time:** 2026-03-18T12:00:00
        - **Execution End Time:** 2026-03-18T12:00:05

        ## Action Log

        ### `CREATE`: [test.txt](/test.txt)
        - **Status:** SUCCESS
        - **Description:** Creating a file.

        ---

        ### `EXECUTE`: "Run tests"
        - **Status:** FAILURE
        - **Return Code:** `1`

        #### `stdout`
        ````text
        Test failed!
        ````
        #### `stderr`
        ````text
        Error: 404
        ````
    """)

    parser = ReportParser(report_content)

    # Assert Summary
    assert parser.summary["Overall Status"] == "SUCCESS"
    assert parser.summary["Execution Start Time"] == "2026-03-18T12:00:00"

    # Assert Action Logs
    logs = parser.action_logs
    expected_action_count = 2
    assert len(logs) == expected_action_count

    # Action 0: CREATE
    assert logs[0].type == "CREATE"
    assert logs[0].status == "SUCCESS"
    assert logs[0].params["File Path"] == "test.txt"

    # Action 1: EXECUTE
    assert logs[1].type == "EXECUTE"
    assert logs[1].status == "FAILURE"
    assert logs[1].details["return_code"] == 1
    assert logs[1].details["stdout"] == "Test failed!"
    assert logs[1].details["stderr"] == "Error: 404"


def test_action_was_successful_helper():
    """Verifies the ergonomic helper for checking action success."""
    report_content = dedent("""\
        # Execution Report
        - **Overall Status:** SUCCESS

        ## Action Log
        ### `CREATE`: [a.txt](/a.txt)
        - **Status:** SUCCESS
    """)
    parser = ReportParser(report_content)
    assert parser.action_was_successful(0) is True
