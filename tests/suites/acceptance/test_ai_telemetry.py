import yaml
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch
from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


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
    # Using -y to prevent the loop from consuming inputs meant for other checks
    fixed_now = datetime(2026, 4, 17, 12, 0, 0)
    with patch("teddy_executor.core.services.session_service.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        result = adapter.run_start(["--agent", "pathfinder", "-y"], input="My Goal\n")

    assert result.exit_code == 0
    turn_dir = Path(".teddy/sessions/20260417_120000-new-feature/01")
    assert (tmp_path / turn_dir / "input.md").exists()
    assert (tmp_path / turn_dir / "pathfinder.xml").exists()
    import re

    combined_output = result.stdout + (result.stderr or "")
    assert re.search(r"Model:.*gpt-4o", combined_output)
    assert re.search(r"Context:.*15.2k tokens", combined_output)
    assert re.search(r"Session Cost:.*\$0.0400", combined_output)


def test_telemetry_persistence_across_turns(tmp_path, monkeypatch):
    """Verifies cumulative cost persistence."""
    import sys
    import re
    from teddy_executor.core.ports.outbound import ILlmClient, IUserInteractor

    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()

    # Mock interactor to approve the resumption
    mock_interactor = env.get_service(IUserInteractor)
    mock_interactor.confirm_action.return_value = (True, "")
    # In the new silent flow, turn 2 will proceed without asking for a question if turn 1 was SUCCESS.
    # We only need one 'yes' for the initial start, and then an empty string to terminate
    # if the loop eventually prompts again.
    mock_interactor.ask_question.side_effect = ["yes", ""]
    mock_interactor.display_message.side_effect = lambda m: print(m, file=sys.stdout)

    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_telemetry_env(tmp_path)

    mock_llm_client = env.get_service(ILlmClient)
    # Turn 1
    fixed_now = datetime(2026, 4, 17, 12, 0, 0)
    plan_1 = MarkdownPlanBuilder("Turn 1").add_execute("echo 1").build()
    mock_llm_client.get_completion.return_value = make_mock_response(plan_1)
    mock_llm_client.get_completion_cost.return_value = 0.01
    # Use -y to ensure Turn 1 finishes before we manually trigger Turn 2 via resume
    with patch("teddy_executor.core.services.session_service.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        adapter.run_start(["turn-1", "--agent", "pathfinder", "-y"], input="yes\n")

    # Turn 2
    plan_2 = MarkdownPlanBuilder("Turn 2").add_execute("echo 2").build()
    # Resume Turn 1 and trigger Turn 2 planning.
    # The run_start already consumed the mock's first return value.
    # The run_resume (planning phase) will consume the first element of side_effect.
    mock_llm_client.get_completion.side_effect = [
        make_mock_response(plan_2),
    ]
    # To reach a Session Cost of $0.0300, Turn 2 must add $0.02 to Turn 1's $0.01.
    mock_llm_client.get_completion_cost.side_effect = [0.02]

    result = adapter.run_resume(
        ".teddy/sessions/20260417_120000-turn-1", interactive=False
    )

    assert result.exit_code == 0
    meta_2 = yaml.safe_load(
        (tmp_path / ".teddy/sessions/20260417_120000-turn-1/02/meta.yaml").read_text()
    )
    # Turn 2 meta.yaml inherits the cumulative cost of Turn 1 (0.01)
    # before its own cost (0.02) is added in the next turn transition.
    initial_cost = 0.01
    assert meta_2["cumulative_cost"] == initial_cost
    combined_output = result.stdout + (result.stderr or "")
    # Session Cost = inherited cumulative_cost (0.01) + current turn_cost (0.02) = 0.03
    assert re.search(r"Session Cost:.*\$0.0300", combined_output)


def test_input_log_during_replan(tmp_path, monkeypatch):
    """Verifies input.md during re-planning."""
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

    fixed_now = datetime(2026, 4, 17, 12, 0, 0)
    with patch("teddy_executor.core.services.session_service.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        result = adapter.run_start(["replan-test", "-y"], input="Go\n")

    assert result.exit_code == 1
    assert (
        tmp_path / ".teddy/sessions/20260417_120000-replan-test/02/input.md"
    ).exists()
