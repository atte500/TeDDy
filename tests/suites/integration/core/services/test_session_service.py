from datetime import datetime, timezone
from pathlib import Path
from teddy_executor.core.domain.models.session import SessionOptions
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.time_service import ITimeService


def _ledger_snapshot(session_dir: Path) -> dict[str, bytes]:
    """
    Snapshots a session's core ledger files for byte-identity assertions
    (session.context, agent prompt, and 01/meta.yaml).
    """
    return {
        "session.context": (session_dir / "session.context").read_bytes(),
        "developer.xml": (session_dir / "developer.xml").read_bytes(),
        "01/meta.yaml": (session_dir / "01" / "meta.yaml").read_bytes(),
    }


def test_transition_to_next_turn_handles_missing_turn_context(tmp_path, container):
    """
    Scenario: Fix Session Service FileNotFoundError (Refactoring)
    Given a session transition is triggered.
    And the turn.context file is missing in the current turn directory.
    When SessionService.transition_to_next_turn is called.
    Then it MUST NOT raise a FileNotFoundError.
    And it MUST treat the missing file as an empty context.
    """
    # Arrange
    service = container.resolve(ISessionManager)

    session_dir = tmp_path / ".teddy" / "sessions" / "test-session"
    turn_01_dir = session_dir / "01"
    turn_01_dir.mkdir(parents=True)

    # Setup required files for transition
    (turn_01_dir / "meta.yaml").write_text("turn_id: '01'")
    (turn_01_dir / "pathfinder.xml").write_text("<prompt>test</prompt>")

    # IMPORTANT: turn.context is NOT created here

    plan_path = (turn_01_dir / "plan.md").as_posix()

    # Act
    # This should fail with FileNotFoundError in the current implementation
    next_turn_dir = service.transition_to_next_turn(plan_path)

    # Assert
    next_turn_path = Path(next_turn_dir)
    assert next_turn_path.exists()
    assert (next_turn_path / "turn.context").exists()

    # The context should contain BOTH the plan and report from turn 01
    context_content = (next_turn_path / "turn.context").read_text()
    assert ".teddy/sessions/test-session/01/plan.md" in context_content
    assert ".teddy/sessions/test-session/01/report.md" in context_content


def test_concurrent_session_creation_claims_distinct_root_and_preserves_sibling(
    tmp_path, monkeypatch, env
):
    """
    Scenario: Concurrent session creation (Wiring gate).

    Given a session root ".teddy/sessions/20260417_120000-feat-x" already
    exists with its full ledger,
    When create_session is invoked with the same name within the same second,
    Then the root ".teddy/sessions/20260417_120000-feat-x-2" is claimed
    atomically via exclusive creation,
    And the first session's session.context, prompt file, and 01/meta.yaml are
    byte-identical to before.
    """
    # Arrange
    env.workspace = tmp_path
    env.with_real_filesystem()
    monkeypatch.chdir(tmp_path)

    # Deterministic clock: both sessions share the same second.
    time_mock = env.mock_port(ITimeService)
    fixed_now = datetime(2026, 4, 17, 12, 0, 0)
    time_mock.now.return_value = fixed_now
    time_mock.now_utc.return_value = fixed_now.replace(tzinfo=timezone.utc)

    # Bootstrap the workspace: init.context + agent prompt (canonical source).
    (tmp_path / ".teddy" / "prompts").mkdir(parents=True)
    (tmp_path / ".teddy" / "init.context").write_text("README.md\n", encoding="utf-8")
    (tmp_path / ".teddy" / "prompts" / "developer.xml").write_text(
        "<prompt>developer</prompt>", encoding="utf-8"
    )

    # Pre-create the concurrent winner's session with its full ledger.
    sibling = tmp_path / ".teddy" / "sessions" / "20260417_120000-feat-x"
    (sibling / "01").mkdir(parents=True)
    (sibling / "session.context").write_text("README.md\n", encoding="utf-8")
    (sibling / "developer.xml").write_text(
        "<prompt>developer</prompt>", encoding="utf-8"
    )
    (sibling / "01" / "meta.yaml").write_text(
        "turn_id: '01'\nagent_name: 'developer'\n", encoding="utf-8"
    )
    before = _ledger_snapshot(sibling)

    # Act
    service = env.get_service(ISessionManager)
    result = service.create_session(
        SessionOptions(name="feat-x", agent_name="developer")
    )

    # Assert: the colliding creator claimed the next free root atomically and
    # all persistence landed on the claimed root.
    assert result == ".teddy/sessions/20260417_120000-feat-x-2"
    claimed = tmp_path / ".teddy" / "sessions" / "20260417_120000-feat-x-2"
    assert (claimed / "01" / "meta.yaml").is_file()
    assert (claimed / "session.context").is_file()
    assert (claimed / "developer.xml").is_file()

    # The concurrent winner's ledger is byte-identical to before.
    after = _ledger_snapshot(sibling)
    assert after == before
