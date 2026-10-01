import pytest
from datetime import datetime
from unittest.mock import Mock
from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from teddy_executor.core.ports.outbound import ILlmClient


def make_mock_response(content, model="gpt-4o"):
    mock_response = Mock()
    mock_response.model = model
    mock_message = Mock()
    mock_message.content = content
    mock_choice = Mock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    return mock_response


def setup_robust_env(tmp_path):
    (tmp_path / ".git").mkdir(exist_ok=True)
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir(exist_ok=True)
    (teddy_dir / "init.context").write_text("README.md", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Test Project", encoding="utf-8")
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    (prompts_dir / "pathfinder.xml").write_text("<prompt/>", encoding="utf-8")


@pytest.mark.timeout(30)
def test_pipeline_message_turn_and_resume_m_round_trip(tmp_path, monkeypatch):
    """Scenario: a pipeline MESSAGE turn stops cleanly and resume -m continues.

    As a script author, I want a `-p` session whose turn ends with a
    MESSAGE action to stop without finalizing the turn, so that I can
    inject the reply via `teddy resume -m` and the session continues
    without re-executing the message turn's plan.
    """
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_robust_env(tmp_path)

    message_plan = (
        MarkdownPlanBuilder("Greeting").with_message("Hi! How are you?").build()
    )
    action_plan = MarkdownPlanBuilder("Follow-up").add_execute("echo 1").build()

    mock_llm = env.get_service(ILlmClient)
    mock_llm.get_completion.return_value = make_mock_response(message_plan)

    from teddy_executor.core.ports.outbound.time_service import ITimeService

    fixed_now = datetime(2026, 4, 17, 12, 0, 0)
    mock_time = env.mock_port(ITimeService)
    mock_time.now.return_value = fixed_now
    mock_time.now_utc.return_value = fixed_now

    # Phase 1: pipeline start — the planned turn is a MESSAGE turn and
    # must stop without finalization (no report.md, no next turn).
    start_result = adapter.run_start(
        ["--pipeline", "-m", "Say hi and ask how I am", "pipe-session"]
    )
    assert start_result.exit_code == 0

    sessions_root = tmp_path / ".teddy" / "sessions"
    session_dirs = list(sessions_root.glob("20260417_120000-*"))
    assert session_dirs, f"No session directory found in {sessions_root}"
    session_dir = session_dirs[0]
    turn01 = session_dir / "01"

    assert (turn01 / "plan.md").exists()
    assert not (turn01 / "report.md").exists(), (
        "A pipeline MESSAGE turn must NOT generate report.md."
    )
    assert not (session_dir / "02").exists(), (
        "A pipeline MESSAGE turn must NOT initialize the next turn."
    )
    meta_text = (turn01 / "meta.yaml").read_text(encoding="utf-8")
    assert "awaiting_reply: true" in meta_text, (
        "The message turn's meta.yaml must flag awaiting_reply: true."
    )
    assert "Hi! How are you?" in start_result.stdout

    # Phase 2: resume with an injected reply — the message turn's plan
    # must NOT be re-executed; the reply plans and executes the next turn.
    mock_llm.get_completion.return_value = make_mock_response(action_plan)
    resume_result = adapter.run_cli_command(
        [
            "resume",
            f".teddy/sessions/{session_dir.name}",
            "--no-copy",
            "-m",
            "I am great, tell me a joke",
        ],
        input="prompt\ny\ny\ny\n",
    )
    assert resume_result.exit_code == 0

    meta_after = (turn01 / "meta.yaml").read_text(encoding="utf-8")
    assert "awaiting_reply" not in meta_after, (
        "The awaiting_reply flag must be cleared once the reply is consumed."
    )
    assert not (turn01 / "report.md").exists(), (
        "The awaiting-reply plan must NOT be re-executed on resume."
    )
    assert (session_dir / "02" / "plan.md").exists()
    assert (session_dir / "02" / "report.md").exists()
