from pathlib import Path
from .helpers import run_teddy_with_plan_structure, parse_yaml_report


def test_successful_execution():
    """
    Given a valid YAML plan with a single 'echo' command,
    When the plan is piped into the teddy command,
    Then the command should exit with status 0,
    And the report should show SUCCESS with the correct output.
    """
    # GIVEN
    plan_structure = [
        {"action": "execute", "params": {"command": 'echo "hello world"'}}
    ]

    # WHEN
    result = run_teddy_with_plan_structure(plan_structure, cwd=Path("."))

    # THEN
    assert result.returncode == 0
    report = parse_yaml_report(result.stdout)

    assert report["run_summary"]["status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SUCCESS"
    assert "hello world" in action_log["output"]
    # error key exists but is empty string on success for shell adapter
    assert not action_log["error"]


def test_failed_execution():
    """
    Given a valid YAML plan with a failing command,
    When the plan is piped into the teddy command,
    Then the command should exit with a non-zero code,
    And the report should show FAILURE with the correct error output.
    """
    # GIVEN
    plan_structure = [
        {"action": "execute", "params": {"command": "nonexistentcommand12345"}}
    ]

    # WHEN
    result = run_teddy_with_plan_structure(plan_structure, cwd=Path("."))

    # THEN
    assert result.returncode != 0
    report = parse_yaml_report(result.stdout)

    assert report["run_summary"]["status"] == "FAILURE"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "FAILURE"
    assert action_log["error"] is not None
    # The specific shell error message for "command not found"
    error_msg = action_log["error"].lower()
    assert "not found" in error_msg or "not recognized" in error_msg
