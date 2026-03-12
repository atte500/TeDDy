from pathlib import Path
from teddy_executor.core.ports.outbound.session_manager import ISessionManager


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

    # The context should only contain the report from turn 01
    context_content = (next_turn_path / "turn.context").read_text()
    assert context_content.strip() == "01/report.md"
