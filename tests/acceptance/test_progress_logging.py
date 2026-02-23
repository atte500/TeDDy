import logging
from typer.testing import CliRunner
from teddy_executor.main import app

runner = CliRunner()


def test_progress_logging_success(capsys, tmp_path, monkeypatch):
    """Scenario 1: Successful Action Execution logs Executing and Success."""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
        force=True,
    )
    monkeypatch.chdir(tmp_path)
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

    stderr_output = capsys.readouterr().err
    assert "Executing Action: READ - Read an existing file" in stderr_output
    assert "Success Action: READ - Read an existing file" in stderr_output


def test_progress_logging_failure(capsys, tmp_path, monkeypatch):
    """Scenario 2: Failed Action Execution logs Executing and Failure."""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
        force=True,
    )
    monkeypatch.chdir(tmp_path)

    plan_content = """
# Test Plan
## Action Plan
### `READ`
- **Resource:** [does_not_exist.txt](/does_not_exist.txt)
- **Description:** Read a missing file
"""
    runner.invoke(app, ["execute", "--plan-content", plan_content, "-y"])

    stderr_output = capsys.readouterr().err
    assert "Executing Action: READ - Read a missing file" in stderr_output
    assert "Failed Action: READ - Read a missing file" in stderr_output
