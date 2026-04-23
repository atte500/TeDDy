from pathlib import Path
from datetime import datetime
from unittest.mock import patch
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment
from teddy_executor.core.ports.outbound import ILlmClient
from tests.suites.acceptance.helpers import setup_project, mock_response


def test_teddy_start_bootstraps_session(tmp_path: Path, monkeypatch):
    """Scenario: 'start' command creates session structure and bootstraps context."""
    env = (
        TestEnvironment(monkeypatch, tmp_path)
        .setup()
        .with_real_shell()
        .with_real_interactor()
    )
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_project(tmp_path)

    llm = env.get_service(ILlmClient)  # type: ignore[type-abstract]
    plan = MarkdownPlanBuilder("Init").add_execute("echo 1").build()
    llm.get_completion.return_value = mock_response(plan)  # type: ignore[attr-defined]

    fixed_now = datetime(2026, 4, 17, 12, 0, 0)
    with patch("teddy_executor.core.services.session_service.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        result = adapter.run_cli_command(["start", "feat-x"], input="instructions\ny\n")

    assert result.exit_code == 0

    session_dir = tmp_path / ".teddy" / "sessions" / "20260417_120000-feat-x"
    assert (session_dir / "01" / "meta.yaml").exists()
    assert (session_dir / "session.context").read_text().strip() == "README.md"
    assert "Pathfinder" in (session_dir / "01" / "pathfinder.xml").read_text()


def test_teddy_resume_executes_pending_plan(tmp_path: Path, monkeypatch):
    """Scenario: 'resume' executes an existing plan if one is pending."""
    (
        TestEnvironment(monkeypatch, tmp_path)
        .setup()
        .with_real_shell()
        .with_real_interactor()
    )
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    turn_dir = tmp_path / ".teddy" / "sessions" / "resume" / "01"
    turn_dir.mkdir(parents=True)
    (turn_dir.parent / "session.context").touch()
    (turn_dir / "turn.context").touch()
    (turn_dir / "pathfinder.xml").touch()
    (turn_dir / "meta.yaml").write_text("turn_id: '01'")

    plan = MarkdownPlanBuilder("Resume").add_execute("echo hello").build()
    (turn_dir / "plan.md").write_text(plan, encoding="utf-8")

    result = adapter.run_cli_command(["resume", "-y"], cwd=turn_dir)
    assert result.exit_code == 0

    # In sessions, execution report is silent in console. Check file.
    report_file = turn_dir / "report.md"
    assert "hello" in report_file.read_text()
    assert (turn_dir / "report.md").exists()
    assert (turn_dir.parent / "02").exists()


def test_teddy_resume_prompts_for_new_plan(tmp_path: Path, monkeypatch):
    """Scenario: 'resume' prompts for input if no plan exists for the current turn."""
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    turn_dir = tmp_path / ".teddy" / "sessions" / "resume-new" / "02"
    turn_dir.mkdir(parents=True)
    (turn_dir.parent / "session.context").touch()
    (turn_dir / "turn.context").touch()
    (turn_dir / "pathfinder.xml").touch()
    (turn_dir / "meta.yaml").write_text("turn_id: '02'\nparent_turn_id: '01'")

    llm = env.get_service(ILlmClient)  # type: ignore[type-abstract]
    plan = MarkdownPlanBuilder("New").add_execute("echo 1").build()
    llm.get_completion.return_value = mock_response(plan)  # type: ignore[attr-defined]

    result = adapter.run_cli_command(["resume"], cwd=turn_dir, input="My Goal\n")
    assert result.exit_code == 0

    assert (turn_dir / "plan.md").exists()
    sent = llm.get_completion.call_args[1]["messages"][1]["content"]  # type: ignore[attr-defined]
    assert "My Goal" in sent and "alignment" in sent


def test_teddy_start_dynamic_renaming_and_flow(tmp_path: Path, monkeypatch):
    """Scenario: Session is dynamically renamed based on the generated plan title."""
    env = (
        TestEnvironment(monkeypatch, tmp_path)
        .setup()
        .with_real_shell()
        .with_real_interactor()
    )
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_project(tmp_path)

    llm = env.get_service(ILlmClient)  # type: ignore[type-abstract]
    plan = MarkdownPlanBuilder("Auth Feature").add_execute("echo 'auth'").build()
    llm.get_completion.return_value = mock_response(plan)  # type: ignore[attr-defined]

    fixed_now = datetime(2026, 4, 17, 12, 0, 0)
    with patch("teddy_executor.core.services.session_service.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        result = adapter.run_cli_command(["start"], input="My prompt\ny\n")

    assert result.exit_code == 0

    assert (
        tmp_path
        / ".teddy"
        / "sessions"
        / "20260417_120000-auth-feature"
        / "01"
        / "report.md"
    ).exists()


def test_teddy_resume_continuous_loop(tmp_path: Path, monkeypatch):
    """Scenario: 'resume' continuously loops until the user exits."""
    env = (
        TestEnvironment(monkeypatch, tmp_path)
        .setup()
        .with_real_shell()
        .with_real_interactor()
    )
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    turn_dir = tmp_path / ".teddy" / "sessions" / "loop-session" / "01"
    turn_dir.mkdir(parents=True)
    (turn_dir.parent / "session.context").touch()
    (turn_dir / "turn.context").touch()
    (turn_dir / "pathfinder.xml").touch()
    (turn_dir / "meta.yaml").write_text("turn_id: '01'")

    llm = env.get_service(ILlmClient)  # type: ignore[type-abstract]

    # First plan
    plan1 = MarkdownPlanBuilder("Plan 1").add_execute("echo turn1").build()
    # Second plan (Fail to break silent loop and force prompt for Turn 03)
    plan2 = MarkdownPlanBuilder("Plan 2").add_execute("exit 1").build()

    llm.get_completion.side_effect = [mock_response(plan1), mock_response(plan2)]

    # Input sequence (Silent Flow R-10-12):
    # 1. Provide goal for Turn 01
    # 2. Approve Plan 1 (y)
    # 3. Turn 02 starts automatically (no prompt)
    # 4. Approve Plan 2 (y)
    # 5. Empty input to exit the loop (Turn 03 starts and prompts because we provide empty input)
    input_sequence = "Goal 1\ny\ny\n\n"

    result = adapter.run_cli_command(["resume"], cwd=turn_dir, input=input_sequence)

    # Exit code is 1 because the last executed plan (Turn 02) failed
    assert result.exit_code == 1

    # In sessions, execution report is silent in console. Check files.
    report1 = turn_dir.parent / "01" / "report.md"
    report2 = turn_dir.parent / "02" / "report.md"
    assert "turn1" in report1.read_text()
    assert "exit 1" in report2.read_text()

    # Verify both turns were executed
    assert (turn_dir.parent / "01" / "report.md").exists()
    assert (turn_dir.parent / "02" / "report.md").exists()


def test_teddy_start_with_explicit_name(tmp_path: Path, monkeypatch):
    """Scenario: 'start' with an explicit name disables dynamic renaming."""
    env = (
        TestEnvironment(monkeypatch, tmp_path)
        .setup()
        .with_real_shell()
        .with_real_interactor()
    )
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_project(tmp_path)

    llm = env.get_service(ILlmClient)  # type: ignore[type-abstract]
    plan = MarkdownPlanBuilder("Other").add_execute("echo '1'").build()
    llm.get_completion.return_value = mock_response(plan)  # type: ignore[attr-defined]

    fixed_now = datetime(2026, 4, 17, 12, 0, 0)
    with patch("teddy_executor.core.services.session_service.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        result = adapter.run_cli_command(["start", "fixed-name"], input="prompt\ny\n")

    assert result.exit_code == 0

    assert (tmp_path / ".teddy" / "sessions" / "20260417_120000-fixed-name").exists()
    assert not (tmp_path / ".teddy" / "sessions" / "20260417_120000-other").exists()
