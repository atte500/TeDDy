import logging
from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_progress_logging_success(caplog, tmp_path, monkeypatch):
    """Scenario 1: Successful Action Execution logs Executing and Success."""
    monkeypatch.chdir(tmp_path)
    caplog.set_level(logging.INFO)
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("dummy content", encoding="utf-8")

    plan_content = """
# Test Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan
### `READ`
- **Resource:** [test_file.txt](/test_file.txt)
- **Description:** Read an existing file
"""
    runner.invoke(app, ["execute", "--plan-content", plan_content, "-y"])

    assert "READ - Read an existing file" in caplog.text
    assert "SUCCESS" in caplog.text


def test_progress_logging_failure(caplog, tmp_path, monkeypatch):
    """Scenario 2: Failed Action Execution logs Executing and Failure."""
    monkeypatch.chdir(tmp_path)
    caplog.set_level(logging.INFO)

    plan_content = """
# Test Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan
### `READ`
- **Resource:** [does_not_exist.txt](/does_not_exist.txt)
- **Description:** Read a missing file
"""
    runner.invoke(app, ["execute", "--plan-content", plan_content, "-y"])

    assert "READ - Read a missing file" in caplog.text
    assert "FAILURE" in caplog.text


def test_progress_logging_execute_stdout(caplog, tmp_path, monkeypatch):
    """Scenario 3: Execution stdout is logged after success/failure."""
    monkeypatch.chdir(tmp_path)
    caplog.set_level(logging.INFO)

    plan_content = """
# Test Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan
### `EXECUTE`
- **Description:** Run a command
- **Expected Outcome:** prints hello
```shell
echo "hello progress log"
```
"""
    runner.invoke(app, ["execute", "--plan-content", plan_content, "-y"])

    assert "EXECUTE - Run a command" in caplog.text
    assert "SUCCESS" in caplog.text
    assert "hello progress log" not in caplog.text
