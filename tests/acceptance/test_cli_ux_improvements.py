from tests.setup.test_environment import TestEnvironment
from tests.drivers.cli_adapter import CliTestAdapter
from tests.drivers.plan_builder import MarkdownPlanBuilder


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


def test_get_prompt_retrieves_default_prompt_from_root(tmp_path, monkeypatch):
    """Scenario: Get prompt from root prompts directory."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Mock pyperclip to prevent exceptions in headless environment
    monkeypatch.setattr("pyperclip.copy", lambda x: None)

    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "architect.md").write_text("root prompt", encoding="utf-8")
    (tmp_path / ".git").mkdir()

    subdir = tmp_path / "subdir"
    subdir.mkdir()

    result = adapter.run_cli_command(["get-prompt", "architect"], cwd=subdir)
    assert result.exit_code == 0
    assert "root prompt" in result.stdout
    assert "Output copied to clipboard." in result.stdout + result.stderr


def test_get_prompt_fails_for_non_existent_prompt(tmp_path, monkeypatch):
    """Scenario: Attempt to get a non-existent prompt."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    result = adapter.run_cli_command(["get-prompt", "unknown"])
    assert result.exit_code != 0
    assert "Prompt 'unknown' not found." in result.stdout + result.stderr
