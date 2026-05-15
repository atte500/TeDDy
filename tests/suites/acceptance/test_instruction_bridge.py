from pathlib import Path
from unittest.mock import Mock
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.setup.test_environment import TestEnvironment
from teddy_executor.core.ports.outbound.llm_client import ILlmClient


def make_mock_response(content, model="gpt-4o"):
    mock_response = Mock()
    mock_response.model = model
    mock_message = Mock()
    mock_message.content = content
    mock_choice = Mock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    return mock_response


def test_resume_uses_discovery_protocol(tmp_path: Path, monkeypatch):
    """Scenario: AI discovers the goal from initial_request.md when no message is provided."""
    env = TestEnvironment(monkeypatch, tmp_path).setup()
    cli = CliTestAdapter(monkeypatch, tmp_path)

    session_name = "bridge-test"
    turn_dir = tmp_path / ".teddy" / "sessions" / session_name / "01"
    turn_dir.mkdir(parents=True)

    # Discovery Protocol: Goal is in session context via initial_request.md
    goal_content = "My Discovery Goal"
    (turn_dir.parent / "initial_request.md").write_text(goal_content)
    (turn_dir.parent / "session.context").write_text(
        f".teddy/sessions/{session_name}/initial_request.md"
    )

    (turn_dir / "turn.context").touch()
    (turn_dir / "pathfinder.xml").touch()
    (turn_dir / "meta.yaml").write_text("turn_id: '01'\nagent_name: 'pathfinder'")

    # Mock LLM to return a plan
    llm = env.get_service(ILlmClient)
    plan = MarkdownPlanBuilder("Goal").add_execute("echo 1").build()
    llm.get_completion.return_value = make_mock_response(plan)

    # When I resume without a message
    result = cli.run_cli_command(["resume", session_name, "-y"])
    assert result.exit_code == 0

    # Then the AI MUST discover 'My Discovery Goal' from the context file
    sent_messages = llm.get_completion.call_args[1]["messages"]
    user_content = sent_messages[1]["content"]
    assert goal_content in user_content
