from pathlib import Path
from datetime import datetime
from teddy_executor.core.utils.string import slugify
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment
from teddy_executor.core.ports.outbound import ILlmClient
from tests.suites.acceptance.helpers import setup_project, mock_response


def test_teddy_start_bootstraps_session(tmp_path: Path, monkeypatch):
    """Scenario: 'start' command creates session structure and bootstraps context."""
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_shell()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_project(tmp_path)

    llm = env.get_service(ILlmClient)  # type: ignore[type-abstract]
    plan = MarkdownPlanBuilder("Init").add_execute("echo 1").build()
    llm.get_completion.return_value = mock_response(plan)  # type: ignore[attr-defined]

    from teddy_executor.core.ports.outbound.time_service import ITimeService

    fixed_now = datetime(2026, 4, 17, 12, 0, 0)
    mock_time = env.mock_port(ITimeService)
    mock_time.now.return_value = fixed_now
    mock_time.now_utc.return_value = fixed_now

    result = adapter.run_cli_command(["start", "feat-x", "-y", "-m", "instructions"])

    assert result.exit_code == 0

    session_dir = tmp_path / ".teddy" / "sessions" / "20260417_120000-feat-x"
    assert (session_dir / "01" / "meta.yaml").exists()

    # Verify that session.context bootstraps README.md AND includes the initial request
    context_content = (session_dir / "session.context").read_text()
    assert "README.md" in context_content
    assert "initial_request.md" in context_content
    assert "Pathfinder" in (session_dir / "pathfinder.xml").read_text()


def test_teddy_resume_executes_pending_plan(tmp_path: Path, monkeypatch):
    """Scenario: 'resume' executes an existing plan if one is pending."""
    (TestEnvironment(monkeypatch, tmp_path).setup().with_real_shell())
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
    env = TestEnvironment(monkeypatch, tmp_path).setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    # Use a standard session name pattern to avoid auto-renaming
    session_name = "20260515_120000-resume-new"
    turn_dir = tmp_path / ".teddy" / "sessions" / session_name / "02"
    turn_dir.mkdir(parents=True)
    (turn_dir.parent / "session.context").touch()
    (turn_dir / "turn.context").touch()
    (turn_dir / "pathfinder.xml").touch()
    (turn_dir / "meta.yaml").write_text("turn_id: '02'\nparent_turn_id: '01'")

    llm = env.get_service(ILlmClient)  # type: ignore[type-abstract]
    plan = MarkdownPlanBuilder("New").add_execute("echo 1").build()
    llm.get_completion.return_value = mock_response(plan)  # type: ignore[attr-defined]

    # Discovery protocol: My Goal is in initial_request.md (seeded during setup or start)
    (turn_dir.parent / "initial_request.md").write_text("My Goal")
    (turn_dir.parent / "session.context").write_text(
        f".teddy/sessions/{session_name}/initial_request.md"
    )

    result = adapter.run_cli_command(["resume", "-y"], cwd=turn_dir)
    assert result.exit_code == 0

    assert (turn_dir / "plan.md").exists()
    sent = llm.get_completion.call_args[1]["messages"][1]["content"]  # type: ignore[attr-defined]
    # AI discovers 'My Goal' by reading the context file
    assert "My Goal" in sent


def test_teddy_start_dynamic_renaming_and_flow(tmp_path: Path, monkeypatch):
    """Scenario: Session is dynamically renamed based on the generated plan title."""
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_shell()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_project(tmp_path)

    llm = env.get_service(ILlmClient)  # type: ignore[type-abstract]
    plan = MarkdownPlanBuilder("Auth Feature").add_execute("echo 'auth'").build()
    llm.get_completion.return_value = mock_response(plan)  # type: ignore[attr-defined]

    from teddy_executor.core.ports.outbound.time_service import ITimeService

    user_input = "My prompt"
    fixed_now = datetime(2026, 4, 17, 12, 0, 0)
    mock_time = env.mock_port(ITimeService)
    mock_time.now.return_value = fixed_now
    mock_time.now_utc.return_value = fixed_now

    result = adapter.run_cli_command(["start", "-y", "-m", user_input])

    assert result.exit_code == 0
    timestamp = fixed_now.strftime("%Y%m%d_%H%M%S")
    session_name = f"{timestamp}-{slugify(user_input)}"

    assert (
        tmp_path / ".teddy" / "sessions" / session_name / "01" / "report.md"
    ).exists()


def test_teddy_resume_continuous_loop(tmp_path: Path, monkeypatch):
    """Scenario: 'resume' continuously loops until the user exits."""
    monkeypatch.setenv("TEDDY_MAX_TURNS", "2")
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

    # Session mode does NOT exit on failure; it continues the loop.
    assert result.exit_code == 0

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

    from teddy_executor.core.ports.outbound.time_service import ITimeService

    fixed_now = datetime(2026, 4, 17, 12, 0, 0)
    mock_time = env.mock_port(ITimeService)
    mock_time.now.return_value = fixed_now
    mock_time.now_utc.return_value = fixed_now

    result = adapter.run_cli_command(["start", "fixed-name"], input="prompt\ny\n")

    assert result.exit_code == 0

    assert (tmp_path / ".teddy" / "sessions" / "20260417_120000-fixed-name").exists()
    assert not (tmp_path / ".teddy" / "sessions" / "20260417_120000-other").exists()


def test_teddy_start_loops_multiple_turns_when_non_interactive_yes(
    tmp_path: Path, monkeypatch
):
    """Scenario: 'start' with -y and -m runs multiple turns automatically up to loop guard limit."""
    monkeypatch.setenv("TEDDY_MAX_TURNS", "2")
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_shell()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_project(tmp_path)

    llm = env.get_service(ILlmClient)  # type: ignore[type-abstract]
    plan1 = MarkdownPlanBuilder("Plan 1").add_execute("echo turn1").build()
    plan2 = MarkdownPlanBuilder("Plan 2").add_execute("echo turn2").build()
    llm.get_completion.side_effect = [mock_response(plan1), mock_response(plan2)]  # type: ignore[attr-defined]

    result = adapter.run_cli_command(["start", "-y", "-m", "Goal"])

    assert result.exit_code == 0

    # Locate the session directory (it will have a timestamp)
    session_dirs = list((tmp_path / ".teddy" / "sessions").glob("*"))
    assert len(session_dirs) == 1
    session_dir = session_dirs[0]

    # Both Turn 1 and Turn 2 should have executed and generated reports
    assert (session_dir / "01" / "report.md").exists()
    assert (session_dir / "02" / "report.md").exists()
    assert "turn1" in (session_dir / "01" / "report.md").read_text()
    assert "turn2" in (session_dir / "02" / "report.md").read_text()


def test_teddy_start_prompts_for_message_in_non_interactive_yes(
    tmp_path: Path, monkeypatch
):
    """Scenario: 'start' with -y but no -m prompts the user for the initial message."""
    env = (
        TestEnvironment(monkeypatch, tmp_path)
        .setup()
        .with_real_shell()
        .with_real_interactor()
    )
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_project(tmp_path)

    llm = env.get_service(ILlmClient)  # type: ignore[type-abstract]
    plan = MarkdownPlanBuilder("My Goal").add_execute("echo 1").build()
    llm.get_completion.return_value = mock_response(plan)  # type: ignore[attr-defined]

    # Provide the initial message followed by enter
    result = adapter.run_cli_command(["start", "-y"], input="Interactive Goal Input\n")

    assert result.exit_code == 0

    # Locate the session directory
    session_dirs = list((tmp_path / ".teddy" / "sessions").glob("*"))
    assert len(session_dirs) == 1
    session_dir = session_dirs[0]

    # Verify initial request file content
    assert (
        session_dir / "initial_request.md"
    ).read_text().strip() == "Interactive Goal Input"


def test_teddy_start_aborts_on_empty_message_in_non_interactive_yes(
    tmp_path: Path, monkeypatch
):
    """Scenario: 'start' with -y and no -m raises EOFError/aborts if input is empty or closed."""
    (
        TestEnvironment(monkeypatch, tmp_path)
        .setup()
        .with_real_shell()
        .with_real_interactor()
    )
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_project(tmp_path)

    # Empty input should cause an abort
    result = adapter.run_cli_command(["start", "-y"], input="")

    assert result.exit_code != 0


def test_teddy_non_interactive_auto_pruning_and_physical_removal(
    tmp_path: Path, monkeypatch
):
    """
    Scenario: Under non-interactive (-y) execution, pruning heuristics apply,
    unselected files are harvested programmatically into plan metadata, and
    excluded from the next turn's context file on disk.
    """
    TestEnvironment(monkeypatch, tmp_path).setup().with_real_shell()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_project(tmp_path)

    # 1. Create a session layout for Turn 02.
    session_dir = tmp_path / ".teddy" / "sessions" / "20260515_120000-prune-non-int"
    turn_02_dir = session_dir / "02"
    turn_02_dir.mkdir(parents=True)

    # Turn 01 was a validation failure. Let's write the failure report and plan.
    turn_01_dir = session_dir / "01"
    turn_01_dir.mkdir(parents=True)
    turn_01_plan = turn_01_dir / "plan.md"
    turn_01_plan.write_text("# Turn 1 Plan")
    turn_01_report = turn_01_dir / "report.md"
    # Specify the exact validation failure indicator
    turn_01_report.write_text("# Report 1\n- **Overall Status:** Validation Failed")

    # Let's write files that will be in Turn 02 turn.context
    readme = tmp_path / "README.md"
    readme.write_text("Readme contents")

    # Seed the Turn 02 context
    turn_02_context = turn_02_dir / "turn.context"
    # It tracks README.md and the failed Turn 01 plan and report
    turn_02_context.write_text(
        "README.md\n"
        ".teddy/sessions/20260515_120000-prune-non-int/01/plan.md\n"
        ".teddy/sessions/20260515_120000-prune-non-int/01/report.md"
    )

    # Also touch the session.context
    (session_dir / "session.context").write_text("README.md\ninitial_request.md")
    (session_dir / "initial_request.md").write_text("My Goal")

    # Setup standard metadata for Turn 02
    (turn_02_dir / "meta.yaml").write_text("turn_id: '02'\nagent_name: pf")
    (turn_02_dir / "pathfinder.xml").touch()

    # The plan to execute for Turn 02
    plan2 = (
        MarkdownPlanBuilder("Turn 2")
        .with_rationale("Executing next step.")
        .add_execute("echo turn2")
        .build()
    )
    (turn_02_dir / "plan.md").write_text(plan2)

    # Run the resume command in non-interactive mode
    result = adapter.run_cli_command(["resume", "-y"], cwd=turn_02_dir)
    assert result.exit_code == 0

    # Turn 03 should have been created
    turn_03_dir = session_dir / "03"
    assert turn_03_dir.exists()

    # The next turn's turn.context should be written to disk
    turn_03_context = turn_03_dir / "turn.context"
    assert turn_03_context.exists()
    turn_03_context_content = turn_03_context.read_text()

    # Since Turn 01 failed validation, it must be auto-pruned and physically excluded
    # from the next turn's turn.context!
    assert "01/plan.md" not in turn_03_context_content
    assert "01/report.md" not in turn_03_context_content

    # However, README.md (the clean file) should still be in turn.context
    assert "README.md" in turn_03_context_content
