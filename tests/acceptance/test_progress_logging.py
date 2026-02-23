import logging
from typer.testing import CliRunner
from teddy_executor.main import app

runner = CliRunner()


def test_progress_logging_success(caplog, tmp_path, monkeypatch):
    """Scenario 1: Successful Action Execution logs Executing and Success."""
    monkeypatch.chdir(tmp_path)
    caplog.set_level(logging.INFO)
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("dummy content", encoding="utf-8")

    plan_content = """
# Test Plan
## Action Plan
### `READ`
- **Resource:** [test_file.txt](/test_file.txt)
- **Description:** Read an existing file
"""
    runner.invoke(app, ["execute", "--plan-content", plan_content, "-y"])

    assert "Executing: READ" in caplog.text, "Expected 'Executing: READ' in log output"
    assert "Success: READ" in caplog.text, "Expected 'Success: READ' in log output"


def test_progress_logging_failure(caplog, tmp_path, monkeypatch):
    """Scenario 2: Failed Action Execution logs Executing and Failure."""
    monkeypatch.chdir(tmp_path)
    caplog.set_level(logging.INFO)

    plan_content = """
# Test Plan
## Action Plan
### `READ`
- **Resource:** [does_not_exist.txt](/does_not_exist.txt)
- **Description:** Read a missing file
"""
    runner.invoke(app, ["execute", "--plan-content", plan_content, "-y"])

    assert "Executing: READ" in caplog.text, "Expected 'Executing: READ' in log output"
    assert "Failure: READ" in caplog.text, "Expected 'Failure: READ' in log output"
