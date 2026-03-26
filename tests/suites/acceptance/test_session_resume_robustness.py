import time
import pytest
from unittest.mock import MagicMock
from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from teddy_executor.core.ports.outbound import ILlmClient


def make_mock_response(content, model="gpt-4o"):
    mock_response = MagicMock()
    mock_response.model = model
    mock_message = MagicMock()
    mock_message.content = content
    mock_choice = MagicMock()
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


@pytest.mark.timeout(5)
def test_resume_auto_detects_latest_session(tmp_path, monkeypatch):
    """Scenario: 'resume' without args picks the most recent session."""
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_robust_env(tmp_path)

    plan = MarkdownPlanBuilder("Test").add_execute("echo 1").build()
    mock_llm = env.get_service(ILlmClient)
    mock_llm.get_completion.return_value = make_mock_response(plan)

    adapter.run_start(["older-session"], input="prompt\ny\n")
    time.sleep(0.1)
    adapter.run_start(["newer-session"], input="prompt\ny\n")

    result = adapter.run_cli_command(["resume"], input="prompt\ny\ny\ny\n")

    assert result.exit_code == 0
    assert "newer-session" in result.stdout
    assert "older-session" not in result.stdout


def test_resume_with_session_path(tmp_path, monkeypatch):
    """Scenario: 'resume' works with an explicit session path."""
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_robust_env(tmp_path)

    plan = MarkdownPlanBuilder("Test").add_execute("echo 1").build()
    env.get_service(ILlmClient).get_completion.return_value = make_mock_response(plan)

    adapter.run_start(["my-session"], input="prompt\ny\n")

    result = adapter.run_cli_command(
        ["resume", ".teddy/sessions/my-session"], input="prompt\ny\n"
    )

    assert result.exit_code == 0
    assert "my-session" in result.stdout


def test_resume_with_turn_path(tmp_path, monkeypatch):
    """Scenario: 'resume' resolves session name from a turn path."""
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_robust_env(tmp_path)

    plan = MarkdownPlanBuilder("Test").add_execute("echo 1").build()
    env.get_service(ILlmClient).get_completion.return_value = make_mock_response(plan)

    adapter.run_start(["my-session"], input="prompt\ny\n")

    result = adapter.run_cli_command(
        ["resume", ".teddy/sessions/my-session/01"], input="prompt\ny\n"
    )

    assert result.exit_code == 0
    assert "my-session" in result.stdout


def test_start_enters_continuous_loop(tmp_path, monkeypatch):
    """Scenario: 'start' enters a continuous loop after the first turn."""
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_robust_env(tmp_path)

    # Use a plan that doesn't edit/create to avoid conflict between turn 1 and 2
    plan = MarkdownPlanBuilder("Test Plan").add_execute("echo 1").build()
    mock_llm = env.get_service(ILlmClient)
    mock_llm.get_completion.return_value = make_mock_response(plan)

    # Provide input for TWO turns:
    # Turn 1: "first prompt\n", then "y\n" to approve execution
    # Turn 2: "second prompt\n", then "y\n" to approve execution
    # Then EOF (or we just let it exit if it runs out of input)
    adapter.run_start(["my-loop-session"], input="first prompt\ny\nsecond prompt\ny\n")

    # The session folder name might be auto-renamed to "test-plan" based on H1.
    # We will check if "02" was created in the session directory.
    session_dir = tmp_path / ".teddy" / "sessions" / "test-plan"
    if not session_dir.exists():
        session_dir = tmp_path / ".teddy" / "sessions" / "my-loop-session"

    assert (session_dir / "01" / "report.md").exists()
    assert (session_dir / "02" / "report.md").exists(), (
        "'start' did not enter continuous loop for turn 02."
    )


def test_resume_with_file_path(tmp_path, monkeypatch):
    """Scenario: 'resume' resolves session name from a file path inside a turn."""
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_robust_env(tmp_path)

    plan = MarkdownPlanBuilder("Test").add_execute("echo 1").build()
    env.get_service(ILlmClient).get_completion.return_value = make_mock_response(plan)

    adapter.run_start(["my-session"], input="prompt\ny\n")

    result = adapter.run_cli_command(
        ["resume", ".teddy/sessions/my-session/01/meta.yaml"], input="prompt\ny\n"
    )

    assert result.exit_code == 0
    assert "my-session" in result.stdout
