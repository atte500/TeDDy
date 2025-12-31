import os
import platform
import yaml


from teddy.adapters.inbound.cli_formatter import (
    format_report_as_yaml,
    format_project_context,
)
from teddy.core.domain.models import (
    ExecutionReport,
    ActionResult,
    ExecuteAction,
    ContextResult,
    FileContext,
)


def test_format_project_context():
    """
    Given a ContextResult object,
    When format_project_context is called,
    Then it should return a well-structured string with all context info.
    """
    # Arrange
    context = ContextResult(
        repo_tree="<tree>",
        environment_info={"os": "test_os", "python": "3.x"},
        gitignore_content=".venv/",
        file_contexts=[
            FileContext(
                file_path="src/main.py", content="print('hello')", status="found"
            ),
            FileContext(file_path="non_existent.py", content=None, status="not_found"),
        ],
    )

    # Act
    output = format_project_context(context)

    # Assert
    assert "### Repo Tree ###" in output
    assert "<tree>" in output
    assert "### Environment Info ###" in output
    assert "os: test_os" in output
    assert "python: 3.x" in output
    assert "### .gitignore ###" in output
    assert ".venv/" in output
    assert "### File Contexts ###" in output
    assert "--- File: src/main.py ---" in output
    assert "print('hello')" in output
    assert "--- File: non_existent.py (Not Found) ---" in output


def test_format_report_as_yaml():
    """
    Given an ExecutionReport object,
    When format_report_as_yaml is called,
    Then it should return a valid YAML string with the correct structure.
    """
    # Arrange
    action = ExecuteAction(command="ls -l")
    action_result = ActionResult(
        action=action,
        status="SUCCESS",
        output="total 0",
        error=None,
    )
    report = ExecutionReport(
        run_summary={
            "status": "SUCCESS",
            "duration_seconds": 0.1,
            "start_time": "2023-01-01T12:00:00Z",
        },
        action_logs=[action_result],
    )

    # Act
    yaml_output = format_report_as_yaml(report)

    # Assert
    # Parse the output to verify it's valid YAML
    data = yaml.safe_load(yaml_output)

    assert data["run_summary"]["status"] == "SUCCESS"
    assert "start_time" in data["run_summary"]
    assert "duration_seconds" in data["run_summary"]
    assert data["environment"]["os"] == platform.system()
    assert data["environment"]["cwd"] == str(os.getcwd())

    assert len(data["action_logs"]) == 1
    log = data["action_logs"][0]
    assert log["action"]["type"] == "execute"
    assert log["action"]["params"]["command"] == "ls -l"
    assert log["status"] == "SUCCESS"
    assert log["output"] == "total 0"
    assert log["error"] is None
