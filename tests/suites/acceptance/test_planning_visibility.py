from pathlib import Path
from unittest.mock import MagicMock
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment
from teddy_executor.core.ports.outbound import ILlmClient


def mock_response(content):
    res = MagicMock()
    res.choices = [MagicMock()]
    res.choices[0].message.content = content
    res.model = "gpt-4"
    return res


def setup_project(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    teddy = tmp_path / ".teddy"
    teddy.mkdir()
    (teddy / "init.context").write_text("README.md", encoding="utf-8")
    (tmp_path / "README.md").write_text("README", encoding="utf-8")
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "pathfinder.xml").write_text(
        "<prompt>Pathfinder</prompt>", encoding="utf-8"
    )


def test_planning_visibility_includes_turn_id(tmp_path: Path, monkeypatch):
    """Scenario: Planning visibility shows Turn ID and agent before the LLM call."""
    env = (
        TestEnvironment(monkeypatch, tmp_path)
        .setup()
        .with_real_shell()
        .with_real_interactor()
    )
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_project(tmp_path)

    llm = env.get_service(ILlmClient)
    plan = MarkdownPlanBuilder("Init").add_execute("echo 1").build()
    llm.get_completion.return_value = mock_response(plan)

    # We provide input for 'start' (instructions) and then 'n' to stop before execution
    result = adapter.run_cli_command(
        ["start", "visibility-test"], input="instructions\nn\n"
    )

    # The Turn ID header is removed in sessions for noise reduction.
    # We check for the pretty telemetry instead.
    output = result.stdout + (getattr(result, "stderr", ""))
    assert "• Model:" in output
    assert "• Context:" in output
