from tests.setup.test_environment import TestEnvironment
from tests.drivers.cli_adapter import CliTestAdapter
from tests.drivers.plan_builder import MarkdownPlanBuilder


def test_cli_help_is_descriptive_and_accurate(tmp_path, monkeypatch):
    """Scenario: CLI help verification."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # 1. Test top-level help
    result = adapter.run_cli_command(["--help"])
    assert result.exit_code == 0
    assert "execute" in result.stdout
    assert "context" in result.stdout

    # 2. Test execute help specifically for root-relative mentions
    result_execute = adapter.run_cli_command(["execute", "--help"])
    assert result_execute.exit_code == 0
    assert "root-relative" in result_execute.stdout.lower()


def test_cli_framing_via_execution_report(tmp_path, monkeypatch):
    """Scenario: Verify visual framing of the CLI output via the report."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Test Plan")
        .add_execute("echo 'hello'", description="Just a test")
        .build()
    )

    # Verify the report header serves as the primary framing
    report = adapter.execute_plan(plan)
    assert report.run_summary["Overall Status"] == "SUCCESS"
    assert "Test Plan" in report.stdout


def test_edit_action_shows_prompt_and_details(tmp_path, monkeypatch):
    """Scenario: Interactive prompt for EDIT shows action details."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    (tmp_path / "hello.txt").write_text("line 1\n", encoding="utf-8")

    plan = (
        MarkdownPlanBuilder("Test Plan")
        .add_edit("hello.txt", "line 1", "LINE ONE")
        .build()
    )

    # Run interactively and check stdout/stderr for the prompt
    result = adapter.run_execute_with_plan(plan, input="y\n", interactive=True)

    assert result.exit_code == 0
    # Combined output should contain action details
    output = result.stdout + result.stderr
    assert "Action: EDIT" in output
    assert "hello.txt" in output
    assert "SUCCESS" in output


def test_create_action_shows_prompt_and_details(tmp_path, monkeypatch):
    """Scenario: Interactive prompt for CREATE shows action details."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    content = "New file content"
    plan = MarkdownPlanBuilder("Test Plan").add_create("new.txt", content).build()

    result = adapter.run_execute_with_plan(plan, input="y\n", interactive=True)

    assert result.exit_code == 0
    output = result.stdout + result.stderr
    assert "Action: CREATE" in output
    assert "new.txt" in output
    assert "SUCCESS" in output
