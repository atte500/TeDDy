from tests.setup.test_environment import TestEnvironment
from tests.drivers.cli_adapter import CliTestAdapter
from tests.drivers.plan_builder import MarkdownPlanBuilder


def test_global_timeout_enforcement(monkeypatch, tmp_path):
    """Scenario: Verifies that a command exceeding the global timeout is terminated."""
    TestEnvironment(monkeypatch, tmp_path).setup().with_real_shell()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # 1. Setup a local config with a very short timeout
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir(parents=True)
    config_file = teddy_dir / "config.yaml"
    config_file.write_text(
        "execution:\n  default_timeout_seconds: 0.1\n", encoding="utf-8"
    )

    # 2. Define a plan with a command that takes longer than 0.1 second
    plan = (
        MarkdownPlanBuilder("Hanging Plan")
        .add_execute(
            'python -c "import time; time.sleep(0.5)"', description="Hanging command"
        )
        .build()
    )

    # 3. Execute the plan.
    report = adapter.execute_plan(plan, user_input="y\n")

    # 4. Assertions
    assert "timed out" in report.stdout.lower()
    assert report.action_was_successful(0) is False


def test_timeout_captures_partial_output(monkeypatch, tmp_path):
    """Scenario: Verifies that partial output generated before a timeout is captured."""
    TestEnvironment(monkeypatch, tmp_path).setup().with_real_shell()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # 1. Setup a local config with a short timeout
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir(parents=True, exist_ok=True)
    config_file = teddy_dir / "config.yaml"
    config_file.write_text(
        "execution:\n  default_timeout_seconds: 0.5\n", encoding="utf-8"
    )

    # 2. Define a plan with a command that prints then hangs
    script = (
        "import sys, time; print('Partial progress'); sys.stdout.flush(); time.sleep(2)"
    )
    plan = (
        MarkdownPlanBuilder("Partial Output Plan")
        .add_execute(f'python -c "{script}"', description="Prints then hangs")
        .build()
    )

    # 3. Execute the plan.
    report = adapter.execute_plan(plan, user_input="y\n")

    # 4. Assertions
    entry = report.action_logs[0]
    assert "Partial progress" in entry.details.get("stdout", "")
    assert "timed out after 0.5 seconds" in report.stdout.lower()
    assert "124" in report.stdout  # The exit code for timeout should be in the report


def test_intentional_background_execution(monkeypatch, tmp_path):
    """Scenario: Verifies that a command can be run in the background."""
    TestEnvironment(monkeypatch, tmp_path).setup().with_real_shell()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # 1. Define a plan with a background command
    plan = (
        MarkdownPlanBuilder("Background Plan")
        .add_execute('python -c "import time; time.sleep(5)"', background=True)
        .build()
    )

    # 2. Execute the plan with a timing check
    import time

    start_time = time.time()
    report = adapter.execute_plan(plan, user_input="y\n")
    end_time = time.time()

    # 3. Assertions
    MAX_BACKGROUND_STARTUP_SECONDS = 2.0
    assert (
        end_time - start_time < MAX_BACKGROUND_STARTUP_SECONDS
    )  # Should be much faster than 5s
    assert report.action_was_successful(0) is True
    assert "SUCCESS: Background process started with PID" in report.stdout


def test_explicit_timeout_override(monkeypatch, tmp_path):
    """Scenario: Verifies that a specific 'Timeout' in the action metadata overrides default."""
    TestEnvironment(monkeypatch, tmp_path).setup().with_real_shell()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # 1. Setup a local config with a very short timeout (0.5s)
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir(parents=True, exist_ok=True)
    config_file = teddy_dir / "config.yaml"
    config_file.write_text(
        "execution:\n  default_timeout_seconds: 0.5\n", encoding="utf-8"
    )

    # 2. Define a plan with an explicit timeout override (5s)
    plan = (
        MarkdownPlanBuilder("Timeout Override Plan")
        .add_execute(
            "python -c \"import time; time.sleep(1.0); print('Success')\"", timeout=5
        )
        .build()
    )

    # 3. Execute the plan.
    report = adapter.execute_plan(plan, user_input="y\n")

    # 4. Assertions
    assert report.action_was_successful(0) is True
    entry = report.action_logs[0]
    assert "Success" in entry.details.get("stdout", "")
