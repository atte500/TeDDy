from unittest.mock import MagicMock
from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from teddy_executor.core.ports.outbound import ILlmClient


def make_mock_response(content, model="gpt-4o"):
    mock_response = MagicMock()
    mock_response.model = model
    mock_response.cost = 0.0
    mock_message = MagicMock()
    mock_message.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    return mock_response


def setup_init_env(tmp_path):
    (tmp_path / ".git").mkdir()
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    (teddy_dir / "init.context").write_text("README.md", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Test Project", encoding="utf-8")
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "pathfinder.xml").write_text("<prompt>PF</prompt>", encoding="utf-8")


def test_teddy_start_triggers_planning(tmp_path, monkeypatch):
    """Scenario: 'start' triggers planning immediately and accepts goal."""
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_init_env(tmp_path)

    plan = MarkdownPlanBuilder("Init").add_execute("echo 1").build()
    mock_llm = env.get_service(ILlmClient)
    mock_llm.get_completion.return_value = make_mock_response(plan)

    # Input: instructions -> confirmation for plan execution (y)
    result = adapter.run_start(["my-feature"], input="Initial instructions\ny\n")

    assert result.exit_code == 0
    plan_file = tmp_path / ".teddy" / "sessions" / "my-feature" / "01" / "plan.md"
    assert plan_file.exists()

    # Verify instructions were sent to LLM
    call_args = mock_llm.get_completion.call_args[1]
    assert "Initial instructions" in call_args["messages"][1]["content"]
