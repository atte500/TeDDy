from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


def test_cli_interactive_prompt_formatting(tmp_path, monkeypatch):
    """Scenario: Interactive prompt follows the 'Action: TYPE' format."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Prompt Format")
        .add_create("test.txt", "content", description="Make file")
        .build()
    )

    result = adapter.run_execute_with_plan(plan, input="y\n", interactive=True)

    assert result.exit_code == 0
    output = result.stdout + result.stderr
    assert "Action: CREATE" in output
    assert "Description: Make file" in output


def test_get_prompt_retrieves_override_prompt_from_local_config(tmp_path, monkeypatch):
    """Scenario: Get prompt from .teddy/prompts override directory."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Mock pyperclip to prevent exceptions in headless environment
    monkeypatch.setattr("pyperclip.copy", lambda x: None)

    override_dir = tmp_path / ".teddy" / "prompts"
    override_dir.mkdir(parents=True)
    (override_dir / "architect.xml").write_text("override prompt", encoding="utf-8")

    subdir = tmp_path / "subdir"
    subdir.mkdir()

    result = adapter.run_cli_command(["get-prompt", "architect"], cwd=subdir)
    assert result.exit_code == 0
    assert "override prompt" in result.stdout
    assert "Output copied to clipboard." in result.stdout + result.stderr


def test_get_prompt_fails_for_non_existent_prompt(tmp_path, monkeypatch):
    """Scenario: Attempt to get a non-existent prompt."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Create .teddy/prompts/ with available prompts to test enriched error message
    prompts_dir = tmp_path / ".teddy" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "architect.xml").write_text("<prompt/>")
    (prompts_dir / "developer.xml").write_text("<prompt/>")

    result = adapter.run_cli_command(["get-prompt", "unknown"])
    assert result.exit_code != 0
    assert (
        "Prompt 'unknown' not found. Available prompts: architect, developer"
        in result.stdout + result.stderr
    )


def test_config_check_message_is_localized_to_start_command(tmp_path, monkeypatch):
    """Scenario: 'Checking configurations...' message is only shown for 'start'."""
    from tests.harness.setup.test_environment import TestEnvironment

    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # 1. Verify message IS present in 'start'
    # Use a dummy message to trigger the handler
    result_start = adapter.run_cli_command(["start", "-m", "test", "--no-interactive"])
    assert "Checking configurations..." in result_start.stderr

    # 2. Verify message is NOT present in 'execute'
    plan = (
        MarkdownPlanBuilder("Test Plan")
        .add_execute("echo 'hello'", description="Test")
        .build()
    )
    result_execute = adapter.run_execute_with_plan(plan, interactive=False)
    assert "Checking configurations..." not in result_execute.stderr

    # 3. Verify message is NOT present in 'context'
    result_context = adapter.run_cli_command(["context", "--no-copy"])
    assert "Checking configurations..." not in result_context.stderr
