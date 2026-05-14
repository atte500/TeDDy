from datetime import datetime
from pathlib import Path
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from teddy_executor.core.ports.outbound import ILlmClient
from tests.suites.acceptance.helpers import setup_project, mock_response


def test_start_session_creates_prefixed_directory(tmp_path: Path, monkeypatch):
    # GIVEN: A fixed time and workspace setup
    env = TestEnvironment(monkeypatch, tmp_path).setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_project(tmp_path)

    fixed_now = datetime(2026, 4, 17, 12, 0, 0)
    expected_prefix = "20260417_120000"
    session_name = "refactor-auth"
    expected_folder = f"{expected_prefix}-{session_name}"

    # Mock LLM to return a valid plan
    llm = env.get_service(ILlmClient)
    plan = MarkdownPlanBuilder("Fix").add_execute("echo 1").build()
    llm.get_completion.return_value = mock_response(plan)

    # WHEN: We start a new session
    from teddy_executor.core.ports.outbound.time_service import ITimeService

    mock_time = env.mock_port(ITimeService)
    mock_time.now.return_value = fixed_now
    mock_time.now_utc.return_value = fixed_now

    # Use -y and -m to avoid interactive prompts in CI
    adapter.run_cli_command(["start", session_name, "-y", "-m", "instructions"])

    # THEN: The session directory must be created with the timestamp prefix
    session_path = tmp_path / ".teddy" / "sessions" / expected_folder
    assert session_path.exists(), (
        f"Expected session folder {expected_folder} not found."
    )
    assert (session_path / "01").exists()
