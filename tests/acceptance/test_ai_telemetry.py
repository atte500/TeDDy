import yaml
from pathlib import Path
from unittest.mock import MagicMock
from tests.setup.test_environment import TestEnvironment
from tests.drivers.cli_adapter import CliTestAdapter
from tests.drivers.plan_builder import MarkdownPlanBuilder


def make_mock_response(content, model="gpt-4o"):
    mock_response = MagicMock()
    mock_response.model = model
    mock_message = MagicMock()
    mock_message.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    return mock_response


def setup_telemetry_env(tmp_path):
    """Common setup for telemetry tests."""
    prompt_dir = tmp_path / ".teddy" / "prompts"
    prompt_dir.mkdir(parents=True)
    (prompt_dir / "pathfinder.xml").write_text(
        "<prompt>Pathfinder Instructions</prompt>", encoding="utf-8"
    )
    (tmp_path / ".teddy" / "init.context").write_text("README.md", encoding="utf-8")
    (tmp_path / "README.md").write_text("Context file content", encoding="utf-8")


def test_ai_telemetry_and_logging(tmp_path, monkeypatch):
    """Scenario: AI Transparency & Telemetry."""
    from teddy_executor.core.ports.outbound import ILlmClient

    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()

    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_telemetry_env(tmp_path)

    plan = (
        MarkdownPlanBuilder("New Feature")
        .add_create("file.txt", "content", description="test")
        .build()
    )
    mock_llm_client = env.get_service(ILlmClient)
    mock_llm_client.get_completion.return_value = make_mock_response(plan)
    mock_llm_client.get_token_count.return_value = 15200
    mock_llm_client.get_completion_cost.return_value = 0.04

    # Input: Goal prompt -> Confirmation for plan execution (y)
    result = adapter.run_start(["--agent", "pathfinder"], input="My Goal\ny\n")

    assert result.exit_code == 0
    turn_dir = Path(".teddy/sessions/new-feature/01")
    assert (tmp_path / turn_dir / "input.log").exists()
    assert (tmp_path / turn_dir / "pathfinder.xml").exists()
    combined_output = result.stdout + (result.stderr or "")
    assert "Model: gpt-4o" in combined_output
    assert "Context: 15.2k tokens" in combined_output
    assert "Session Cost: $0.0400" in combined_output


def test_telemetry_persistence_across_turns(tmp_path, monkeypatch):
    """Verifies cumulative cost persistence."""
    import sys
    from teddy_executor.core.ports.outbound import ILlmClient, IUserInteractor

    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()

    # Mock interactor to approve the resumption
    mock_interactor = env.get_service(IUserInteractor)
    mock_interactor.confirm_action.return_value = (True, "")
    mock_interactor.ask_question.return_value = "yes"
    mock_interactor.display_message.side_effect = lambda m: print(m, file=sys.stdout)

    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_telemetry_env(tmp_path)

    mock_llm_client = env.get_service(ILlmClient)
    # Turn 1
    plan_1 = MarkdownPlanBuilder("Turn 1").add_execute("echo 1").build()
    mock_llm_client.get_completion.return_value = make_mock_response(plan_1)
    mock_llm_client.get_completion_cost.return_value = 0.01
    adapter.run_start(["turn-1", "--agent", "pathfinder"])

    # Turn 2
    plan_2 = MarkdownPlanBuilder("Turn 2").add_execute("echo 2").build()
    mock_llm_client.get_completion.return_value = make_mock_response(plan_2)
    mock_llm_client.get_completion_cost.return_value = 0.02

    result = adapter.run_resume(".teddy/sessions/turn-1")

    assert result.exit_code == 0
    meta_2 = yaml.safe_load(
        (tmp_path / ".teddy/sessions/turn-1/02/meta.yaml").read_text()
    )
    EXPECTED_CUMULATIVE_COST = 0.01
    assert meta_2["cumulative_cost"] == EXPECTED_CUMULATIVE_COST
    combined_output = result.stdout + (result.stderr or "")
    assert "Session Cost: $0.0300" in combined_output


def test_input_log_during_replan(tmp_path, monkeypatch):
    """Verifies input.log during re-planning."""
    from teddy_executor.core.ports.outbound import ILlmClient

    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()

    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_telemetry_env(tmp_path)

    mock_llm_client = env.get_service(ILlmClient)
    bad_plan = (
        MarkdownPlanBuilder("Bad Plan")
        .add_edit("non_existent.py", "find", "replace")
        .build()
    )
    good_plan = MarkdownPlanBuilder("Corrected Plan").add_create("ok.txt", "ok").build()
    mock_llm_client.get_completion.side_effect = [
        make_mock_response(bad_plan),
        make_mock_response(good_plan),
    ]

    result = adapter.run_start(["replan-test"], input="Go\n")
    assert result.exit_code == 1
    assert (tmp_path / ".teddy/sessions/replan-test/02/input.log").exists()
