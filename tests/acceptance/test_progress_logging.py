import logging
from tests.setup.test_environment import TestEnvironment
from tests.drivers.cli_adapter import CliTestAdapter
from tests.drivers.plan_builder import MarkdownPlanBuilder


def test_progress_logging_success(caplog, tmp_path, monkeypatch):
    """Scenario 1: Successful Action Execution logs Executing and Success."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    caplog.set_level(logging.INFO)

    test_file = tmp_path / "test_file.txt"
    test_file.write_text("dummy content", encoding="utf-8")

    plan = (
        MarkdownPlanBuilder("Progress Success")
        .add_read("test_file.txt", description="Read an existing file")
        .build()
    )

    adapter.run_execute_with_plan(plan)

    assert "READ - Read an existing file" in caplog.text
    assert "SUCCESS" in caplog.text


def test_progress_logging_failure(caplog, tmp_path, monkeypatch):
    """Scenario 2: Failed Action Execution logs Executing and Failure."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_shell()  # Real shell needed for exit 1
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    caplog.set_level(logging.INFO)

    plan = (
        MarkdownPlanBuilder("Progress Failure")
        .add_execute("exit 1", description="Fails")
        .build()
    )

    adapter.run_execute_with_plan(plan)

    assert "EXECUTE - Fails" in caplog.text
    assert "FAILURE" in caplog.text


def test_progress_logging_execute_stdout(caplog, tmp_path, monkeypatch):
    """Scenario 3: Execution stdout is NOT logged by default to avoid clutter."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_shell()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    caplog.set_level(logging.INFO)

    plan = (
        MarkdownPlanBuilder("Progress Output")
        .add_execute('echo "hello progress log"', description="Run a command")
        .build()
    )

    adapter.run_execute_with_plan(plan)

    assert "EXECUTE - Run a command" in caplog.text
    assert "SUCCESS" in caplog.text
    assert "hello progress log" not in caplog.text
