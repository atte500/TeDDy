from .helpers import run_execute_with_plan_content
from .plan_builder import MarkdownPlanBuilder


def test_global_timeout_enforcement(monkeypatch, tmp_path):
    """
    Scenario 1: Configurable Global Timeout
    Verifies that a command exceeding the global timeout defined in config is terminated.
    """
    # 1. Setup a local config with a very short timeout
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    config_file = teddy_dir / "config.yaml"
    config_file.write_text(
        "execution:\n  default_timeout_seconds: 0.1\n", encoding="utf-8"
    )

    # 2. Define a plan with a command that takes longer than 0.1 second
    builder = MarkdownPlanBuilder("Hanging Plan")
    builder.add_action(
        "EXECUTE",
        params={"Description": "Run a command that hangs."},
        content_blocks={"COMMAND": ("shell", "sleep 0.5")},
    )
    plan_content = builder.build()

    # 3. Execute the plan.
    result = run_execute_with_plan_content(monkeypatch, plan_content, tmp_path)

    # 4. Assertions
    assert "timed out" in result.stdout.lower()
    assert result.exit_code != 0


def test_timeout_captures_partial_output(monkeypatch, tmp_path):
    """
    Scenario 2: Command Timeout with Partial Output
    Verifies that partial output generated before a timeout is captured and reported.
    """
    # 1. Setup a local config with a short timeout
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    config_file = teddy_dir / "config.yaml"
    config_file.write_text(
        "execution:\n  default_timeout_seconds: 0.5\n", encoding="utf-8"
    )

    # 2. Define a plan with a command that prints then hangs
    # We use a python script to ensure it flushes output so we can capture it.
    script = (
        "import sys, time; print('Partial progress'); sys.stdout.flush(); time.sleep(2)"
    )
    builder = MarkdownPlanBuilder("Partial Output Plan")
    builder.add_action(
        "EXECUTE",
        params={"Description": "Run a command that prints then hangs."},
        content_blocks={"COMMAND": ("shell", f'python3 -c "{script}"')},
    )
    plan_content = builder.build()

    # 3. Execute the plan.
    result = run_execute_with_plan_content(monkeypatch, plan_content, tmp_path)

    # 4. Assertions
    # The partial output should be present in the execution report
    assert "Partial progress" in result.stdout
    # The error message should indicate the timeout
    assert "timed out after 0.5 seconds" in result.stdout.lower()
    # The exit code for timeout should be 124
    # Note: result.exit_code is the CLI's exit code, but we check the report content
    assert "124" in result.stdout


def test_intentional_background_execution(monkeypatch, tmp_path):
    """
    Scenario 3: Intentional Background Execution
    Verifies that a command can be run in the background, returns a PID,
    and doesn't block the executor.
    """
    # 1. Define a plan with a background command
    builder = MarkdownPlanBuilder("Background Plan")
    builder.add_action(
        "EXECUTE",
        params={
            "Description": "Start a background process.",
            "Background": "true",
        },
        content_blocks={"COMMAND": ("shell", "sleep 5")},
    )
    plan_content = builder.build()

    # 2. Execute the plan with a timing check
    import time

    start_time = time.time()
    result = run_execute_with_plan_content(monkeypatch, plan_content, tmp_path)
    end_time = time.time()

    # 3. Assertions
    # It should have finished much faster than the 5-second sleep duration
    max_background_start_time = 2.0
    assert end_time - start_time < max_background_start_time
    assert result.exit_code == 0
    # The output should contain the PID notification
    assert "SUCCESS: Background process started with PID" in result.stdout
