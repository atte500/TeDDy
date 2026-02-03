import yaml


from teddy_executor.adapters.inbound.cli_formatter import (
    format_report_as_yaml,
    format_project_context,
)
from teddy_executor.core.domain.models import ContextResult


def test_format_project_context():
    """
    Given a ContextResult DTO,
    When format_project_context is called,
    Then it should return a string with the four required sections in order,
    and with the correct content and formatting.
    """
    # Arrange
    context = ContextResult(
        system_info={"os": "test_os", "shell": "/bin/test", "python_version": "3.x"},
        repo_tree="src/\n  main.py",
        context_vault_paths=["src/main.py", "README.md", "missing.txt"],
        file_contents={
            "src/main.py": "print('hello')",
            "README.md": "# Title",
            "missing.txt": None,
        },
    )

    # Act
    output = format_project_context(context)

    # Assert
    # 1. Check for all four headers
    assert "# System Information" in output
    assert "# Repository Tree" in output
    assert "# Context Vault" in output
    assert "# File Contents" in output

    # 2. Check content of System Information
    # Note: python_version should be excluded
    assert "os: test_os" in output
    assert "shell: /bin/test" in output
    assert "python_version" not in output

    # 3. Check content of Repository Tree
    assert "src/\n  main.py" in output

    # 4. Check content of Context Vault (clean list)
    assert "```" not in output.split("# Context Vault")[1].split("# File Contents")[0]
    assert "src/main.py" in output
    assert "README.md" in output

    # 5. Check content of File Contents
    assert "--- src/main.py ---" in output
    assert "````python\nprint('hello')\n````" in output
    assert "--- README.md ---" in output
    assert "````markdown\n# Title\n````" in output
    assert "--- missing.txt (Not Found) ---" in output

    # 6. Check order of headers
    assert (
        output.find("# System Information")
        < output.find("# Repository Tree")
        < output.find("# Context Vault")
        < output.find("# File Contents")
    )


def test_format_report_as_yaml():
    """
    Given an ExecutionReport object,
    When format_report_as_yaml is called,
    Then it should return a valid YAML string with the correct structure.
    """
    # Arrange
    from datetime import datetime
    from teddy_executor.core.domain.models import (
        ExecutionReport,
        RunSummary,
        ActionLog,
        RunStatus,
        ActionStatus,
    )

    report = ExecutionReport(
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime(2023, 1, 1, 12, 0, 0),
            end_time=datetime(2023, 1, 1, 12, 1, 0),
        ),
        action_logs=[
            ActionLog(
                status=ActionStatus.SUCCESS,
                action_type="execute",
                params={"command": "ls -l"},
                details={"stdout": "total 0"},
            )
        ],
    )

    # Act
    yaml_output = format_report_as_yaml(report)

    # Assert
    data = yaml.safe_load(yaml_output)
    assert data["run_summary"]["status"] == "SUCCESS"
    assert "start_time" in data["run_summary"]
    assert data["action_logs"][0]["action_type"] == "execute"
    assert data["action_logs"][0]["details"]["stdout"] == "total 0"
