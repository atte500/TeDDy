from teddy_executor.core.domain.models.execution_report import ActionLog, ActionStatus
from teddy_executor.adapters.inbound.textual_plan_reviewer_execution import (
    format_action_log,
)


def test_format_action_log_success():
    """Tests formatting of a successful action log."""
    log = ActionLog(
        action_type="CREATE",
        params={"path": "test.txt"},
        status=ActionStatus.SUCCESS,
        details="File created successfully.",
    )

    formatted = format_action_log(log)

    assert "- **Overall Status:** SUCCESS" in formatted
    assert "### `CREATE`: [test.txt](/test.txt)" in formatted
    assert "- **Status:** SUCCESS" in formatted
    assert "- **Details:** `File created successfully.`" in formatted


def test_format_action_log_failure_with_output():
    """Tests formatting of a failed EXECUTE action with stdout/stderr."""
    log = ActionLog(
        action_type="EXECUTE",
        params={"command": "ls non_existent"},
        status=ActionStatus.FAILURE,
        failed_command="ls non_existent",
        details={
            "return_code": 1,
            "stdout": "out",
            "stderr": "err",
            "diff": "--- a\n+++ b",
            "failed_command": "ls non_existent",
        },
    )

    formatted = format_action_log(log)

    assert "- **Overall Status:** FAILURE" in formatted
    assert "- **Status:** FAILURE" in formatted
    assert "- **Failed Command:** `ls non_existent`" in formatted
    assert "- **Return Code:** `1`" in formatted
    assert "#### `stdout`\n```text\nout\n```" in formatted
    assert "#### `stderr`\n```text\nerr\n```" in formatted
    assert "#### `diff`\n```diff\n--- a\n+++ b\n```" in formatted
