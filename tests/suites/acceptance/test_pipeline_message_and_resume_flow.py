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
    inject the reply via `teddy resume -m`: the session finalizes the
    interrupted turn as a standard message-turn report (no User Request
    section) and continues from there.
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
    assert (turn01 / "report.md").exists(), (
        "The reply must finalize the interrupted turn's report."
    )
    report01 = (turn01 / "report.md").read_text(encoding="utf-8")
    assert "**User Reply:**" in report01, (
        "The finalized report must carry the MESSAGE User Reply block."
    )
    assert "I am great, tell me a joke" in report01, (
        "The finalized report must render the USER's injected reply under "
        "`- **User Reply:**` — never the agent's message (Bug 54 / defect 4b)."
    )
    assert "## User Request" not in report01, (
        "The consumption path must not append a User Request section — "
        "the append applies only when a prior report already exists."
    )
    assert (session_dir / "02" / "plan.md").exists()
    assert (session_dir / "02" / "report.md").exists()


@pytest.mark.timeout(30)
def test_resume_m_on_completed_turn_appends_user_request(tmp_path, monkeypatch):
    """Scenario: `resume -m` on a fully completed turn appends the request.

    As a script author, I want `teddy resume -m` on a session whose
    latest turn is complete to append a smart-fenced `## User Request`
    section to the turn's report and continue into the next turn without
    an interactive prompt, so injected requests join the audit trail
    exactly like a normal user request.
    """
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_robust_env(tmp_path)

    first_plan = MarkdownPlanBuilder("First").add_execute("echo 1").build()
    second_plan = MarkdownPlanBuilder("Second").add_execute("echo 2").build()

    mock_llm = env.get_service(ILlmClient)
    mock_llm.get_completion.return_value = make_mock_response(first_plan)

    from teddy_executor.core.ports.outbound.time_service import ITimeService

    fixed_now = datetime(2026, 4, 17, 12, 0, 0)
    mock_time = env.mock_port(ITimeService)
    mock_time.now.return_value = fixed_now
    mock_time.now_utc.return_value = fixed_now

    # Phase 1: complete turn 01 normally (plan.md + report.md on disk).
    start_result = adapter.run_start(["completed-session"], input="prompt\ny\n")
    assert start_result.exit_code == 0

    session_dirs = list((tmp_path / ".teddy" / "sessions").glob("20260417_120000-*"))
    assert session_dirs, "No session directory found under .teddy/sessions"
    session_dir = session_dirs[0]
    turn01 = session_dir / "01"
    assert (turn01 / "report.md").exists()
    before = (turn01 / "report.md").read_text(encoding="utf-8")
    # The initial-request report may already carry a User Request section;
    # the distinguishing invariant is the COUNT increase plus the injected
    # message content, not section absence.
    assert "Now refactor the parser" not in before

    # Phase 2: resume -m must append the smart-fenced request to the
    # completed turn's report and plan the next turn WITHOUT an
    # interactive prompt (the injected message drives planning).
    mock_llm.get_completion.return_value = make_mock_response(second_plan)
    resume_result = adapter.run_cli_command(
        [
            "resume",
            f".teddy/sessions/{session_dir.name}",
            "--no-copy",
            "-m",
            "Now refactor the parser",
        ],
        input="prompt\ny\ny\ny\n",
    )
    assert resume_result.exit_code == 0

    after = (turn01 / "report.md").read_text(encoding="utf-8")
    assert after.count("## User Request") == before.count("## User Request") + 1, (
        "resume -m on a COMPLETE_TURN must append exactly one new "
        "## User Request section to the latest report."
    )
    assert "Now refactor the parser" in after, (
        "The appended User Request section must carry the injected message."
    )
    assert "```text" in after, (
        "The appended User Request must use a smart-fenced codeblock."
    )

    plan02 = (session_dir / "02" / "plan.md").read_text(encoding="utf-8")
    assert "# Second" in plan02, (
        "The next turn must be planned from the injected message, not an "
        "interactive prompt."
    )
    assert (session_dir / "02" / "report.md").exists()


@pytest.mark.timeout(30)
def test_resume_pipeline_message_finalizes_interrupted_turn(tmp_path, monkeypatch):
    """Scenario: `resume -p -m` finalizes an interrupted pipeline turn.

    As a script author, I want `teddy resume -p -m` on a session whose
    latest turn is an interrupted pipeline MESSAGE turn (awaiting_reply)
    to finalize that turn's report as the standard message-turn shape
    (no `## User Request` section), clear the awaiting_reply flag, and
    continue in pipeline mode from the injected reply.
    """
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_robust_env(tmp_path)

    message_plan = (
        MarkdownPlanBuilder("Greeting").with_message("Hi! How are you?").build()
    )
    followup_plan = (
        MarkdownPlanBuilder("Follow-up").with_message("Great, thanks!").build()
    )

    mock_llm = env.get_service(ILlmClient)
    mock_llm.get_completion.return_value = make_mock_response(message_plan)

    from teddy_executor.core.ports.outbound.time_service import ITimeService

    fixed_now = datetime(2026, 4, 17, 12, 0, 0)
    mock_time = env.mock_port(ITimeService)
    mock_time.now.return_value = fixed_now
    mock_time.now_utc.return_value = fixed_now

    # Phase 1: interrupt a pipeline MESSAGE turn.
    start_result = adapter.run_start(
        ["--pipeline", "-m", "Say hi and ask how I am", "pipe-resume"]
    )
    assert start_result.exit_code == 0

    sessions_root = tmp_path / ".teddy" / "sessions"
    session_dirs = list(sessions_root.glob("20260417_120000-*"))
    assert session_dirs, f"No session directory found in {sessions_root}"
    session_dir = session_dirs[0]
    turn01 = session_dir / "01"
    assert (turn01 / "plan.md").exists()
    assert not (turn01 / "report.md").exists()
    assert not (session_dir / "02").exists()

    # Phase 2: resume -p -m finalizes turn 01 and continues in pipeline mode.
    mock_llm.get_completion.return_value = make_mock_response(followup_plan)
    resume_result = adapter.run_cli_command(
        [
            "resume",
            f".teddy/sessions/{session_dir.name}",
            "--no-copy",
            "--pipeline",
            "-m",
            "I am great, tell me a joke",
        ],
    )
    assert resume_result.exit_code == 0

    # Turn 01 is finalized: standard message-turn report, no User Request.
    assert (turn01 / "report.md").exists()
    report01 = (turn01 / "report.md").read_text(encoding="utf-8")
    assert "**User Reply:**" in report01
    user_reply_section = report01[report01.index("**User Reply:**") :]
    assert "I am great, tell me a joke" in user_reply_section, (
        "The finalized report must render the USER's injected reply under "
        "`- **User Reply:**`."
    )
    assert "Hi! How are you?" not in user_reply_section, (
        "The finalized report must NEVER mislabel the agent's own message as "
        "the user's reply (Bug 54 / defect 4b)."
    )
    assert "## User Request" not in report01
    meta01 = (turn01 / "meta.yaml").read_text(encoding="utf-8")
    assert "awaiting_reply" not in meta01

    # The reply drives the next turn's planning in pipeline mode.
    assert (session_dir / "02" / "plan.md").exists()


@pytest.mark.timeout(30)
def test_resume_pipeline_without_message_stays_awaiting(tmp_path, monkeypatch):
    """Scenario: `resume -p` (no message) re-prints and stays awaiting.

    As a script author, I want `teddy resume -p` with no injected message
    on an interrupted pipeline MESSAGE turn to re-print the agent's
    message and exit WITHOUT creating turn 02 or finalizing, leaving the
    awaiting_reply flag intact for a later reply injection.
    """
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_robust_env(tmp_path)

    message_plan = (
        MarkdownPlanBuilder("Greeting").with_message("Hi! How are you?").build()
    )
    mock_llm = env.get_service(ILlmClient)
    mock_llm.get_completion.return_value = make_mock_response(message_plan)

    from teddy_executor.core.ports.outbound.time_service import ITimeService

    fixed_now = datetime(2026, 4, 17, 12, 0, 0)
    mock_time = env.mock_port(ITimeService)
    mock_time.now.return_value = fixed_now
    mock_time.now_utc.return_value = fixed_now

    start_result = adapter.run_start(
        ["--pipeline", "-m", "Say hi and ask how I am", "pipe-noop"]
    )
    assert start_result.exit_code == 0

    sessions_root = tmp_path / ".teddy" / "sessions"
    session_dirs = list(sessions_root.glob("20260417_120000-*"))
    assert session_dirs, f"No session directory found in {sessions_root}"
    session_dir = session_dirs[0]
    turn01 = session_dir / "01"

    # Act: resume in pipeline mode WITHOUT a message.
    resume_result = adapter.run_cli_command(
        [
            "resume",
            f".teddy/sessions/{session_dir.name}",
            "--no-copy",
            "--pipeline",
        ],
    )
    assert resume_result.exit_code == 0

    # Bug 54 / defect 4a: the stop-again re-print must present the SAME
    # status header + `--- MESSAGE from TeDDy ---` framing as the initial
    # pipeline stop. Both paths route through the shared MESSAGE-rendering
    # helpers, which write to stdout via `typer.secho`.
    def _status_header(output: str, title: str = "Greeting") -> str:
        for line in output.splitlines():
            stripped = line.strip()
            if stripped == title or (
                len(stripped) > len(title)
                and stripped.endswith(title)
                and stripped[0] in "🟢🟡🔴"
            ):
                return stripped
        return ""

    start_output = start_result.stdout + start_result.stderr
    resume_output = resume_result.stdout + resume_result.stderr
    start_header = _status_header(start_output)
    assert start_header, (
        "The initial pipeline stop must present the plan status header."
    )
    assert _status_header(resume_output) == start_header, (
        "The stop-again re-print must present the SAME status header as the "
        "initial pipeline stop (Bug 54 / defect 4a)."
    )
    assert start_output.count("--- MESSAGE from TeDDy ---") == 1
    assert resume_output.count("--- MESSAGE from TeDDy ---") == 1
    assert "Hi! How are you?" in resume_output
    # No turn 02, no finalization, awaiting flag preserved.
    assert not (session_dir / "02").exists()
    assert not (turn01 / "report.md").exists()
    meta01 = (turn01 / "meta.yaml").read_text(encoding="utf-8")
    assert "awaiting_reply: true" in meta01


@pytest.mark.timeout(30)
def test_resume_m_y_on_non_communication_pending_plan_honors_message(
    tmp_path, monkeypatch
):
    """Scenario: `resume -m -y` honors the reply on a pending ACTION turn.

    Given a session whose latest turn has plan.md, NO report.md, and NO
    awaiting_reply flag, and whose plan is NOT a MESSAGE-only turn,
    When I run teddy resume -m "next instruction" -y,
    Then the pending non-communication plan is executed in place,
    And the finalized report renders my message under the "## User Request"
    section (the `-y` facet observable end-to-end — Bug 60).
    """
    (TestEnvironment(monkeypatch, tmp_path).setup().with_real_shell())
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # A NON-communication PENDING_PLAN turn: an EXECUTE-only plan is present,
    # report.md is absent, and meta.yaml carries NO awaiting_reply flag —
    # the exact precondition of the drop site (Bug 60).
    turn_dir = tmp_path / ".teddy" / "sessions" / "resume" / "01"
    turn_dir.mkdir(parents=True)
    (turn_dir.parent / "session.context").touch()
    (turn_dir / "turn.context").touch()
    (turn_dir / "pathfinder.xml").touch()
    (turn_dir / "meta.yaml").write_text("turn_id: '01'")

    pending_plan = MarkdownPlanBuilder("Resume").add_execute("echo honored").build()
    (turn_dir / "plan.md").write_text(pending_plan, encoding="utf-8")

    # Act
    result = adapter.run_cli_command(
        ["resume", "--no-copy", "-m", "next instruction", "-y"], cwd=turn_dir
    )
    assert result.exit_code == 0

    # The pending plan executed IN PLACE and finalized its turn report.
    report_file = turn_dir / "report.md"
    assert report_file.exists(), "The pending non-communication turn must finalize."
    report = report_file.read_text(encoding="utf-8")
    assert "honored" in report, (
        "The pending non-communication plan must execute in place (its "
        "EXECUTE action must run), not be dropped."
    )
    # The injected reply is rendered under ## User Request (the -y facet).
    assert "## User Request" in report, (
        "resume -m -y must render the injected reply under ## User Request."
    )
    assert "next instruction" in report, (
        "The ## User Request section must carry the injected message."
    )
    # Executing the pending turn opens the successor turn.
    assert (turn_dir.parent / "02").exists()
