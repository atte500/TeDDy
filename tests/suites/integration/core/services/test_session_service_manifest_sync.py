"""Integration tests for the live-context manifest sync after MOVE and DELETE.

A rename or removal leaves every manifest that lists the old path pointing at a
path that no longer exists, so ``transition_to_next_turn`` rewrites the next
turn's ``turn.context`` and the session-scoped ``session.context`` from the
successful MOVE and DELETE logs of the report it already receives.
"""

from datetime import datetime, timezone
from pathlib import Path

from teddy_executor.core.domain.models.execution_report import (
    ActionLog,
    ActionStatus,
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.ports.outbound.session_manager import ISessionManager


def _seed_transition(
    tmp_path: Path, turn_context: str, session_context: str | None = None
) -> str:
    """Seeds turn 01 of a session and returns its plan path."""
    session_dir = tmp_path / ".teddy" / "sessions" / "manifest-sync"
    turn_dir = session_dir / "01"
    turn_dir.mkdir(parents=True)
    (turn_dir / "meta.yaml").write_text("turn_id: '01'", encoding="utf-8")
    (turn_dir / "turn.context").write_text(turn_context, encoding="utf-8")
    if session_context is not None:
        (session_dir / "session.context").write_text(session_context, encoding="utf-8")
    return (turn_dir / "plan.md").as_posix()


def _report(*logs: ActionLog) -> ExecutionReport:
    """Builds a successful report carrying the given action logs."""
    now = datetime.now(timezone.utc)
    return ExecutionReport(
        run_summary=RunSummary(status=RunStatus.SUCCESS, start_time=now, end_time=now),
        action_logs=list(logs),
    )


def _log(
    action_type: str,
    params: dict[str, object],
    status: ActionStatus = ActionStatus.SUCCESS,
) -> ActionLog:
    """Builds an action log carrying the parsed plan vocabulary."""
    return ActionLog(status=status, action_type=action_type, params=params)


def _entries(context_file: Path) -> set[str]:
    """Reads a manifest into its set of listed paths."""
    return set(context_file.read_text(encoding="utf-8").splitlines())


def test_move_rewrites_the_listed_path_in_both_manifests(tmp_path, container):
    """
    Given turn.context and session.context listing src/app/old_name.py,
    When a MOVE relocates it to src/app/new_name.py,
    Then both manifests list the new path and neither lists the old one.
    """
    # Arrange
    plan_path = _seed_transition(
        tmp_path,
        turn_context="src/app/old_name.py\nsrc/app/other.py",
        session_context="src/app/old_name.py",
    )
    service = container.resolve(ISessionManager)
    report = _report(
        _log(
            "MOVE",
            {"source": "src/app/old_name.py", "destination": "src/app/new_name.py"},
        )
    )

    # Act
    next_turn = Path(service.transition_to_next_turn(plan_path, report))

    # Assert
    turn_entries = _entries(next_turn / "turn.context")
    assert "src/app/new_name.py" in turn_entries
    assert "src/app/old_name.py" not in turn_entries
    assert "src/app/other.py" in turn_entries

    session_entries = _entries(next_turn.parent / "session.context")
    assert "src/app/new_name.py" in session_entries
    assert "src/app/old_name.py" not in session_entries


def test_directory_move_relocates_every_entry_beneath_the_old_prefix(
    tmp_path, container
):
    """
    Given turn.context listing two files under src/app/legacy,
    When a MOVE renames the directory to src/app/modern,
    Then every entry beneath the old prefix moves with it.
    """
    # Arrange
    plan_path = _seed_transition(
        tmp_path,
        turn_context=(
            "src/app/legacy/engine.py\nsrc/app/legacy/ui.py\nsrc/app/keep.py"
        ),
    )
    service = container.resolve(ISessionManager)
    report = _report(
        _log("MOVE", {"source": "src/app/legacy", "destination": "src/app/modern"})
    )

    # Act
    next_turn = Path(service.transition_to_next_turn(plan_path, report))

    # Assert
    turn_entries = _entries(next_turn / "turn.context")
    assert "src/app/modern/engine.py" in turn_entries
    assert "src/app/modern/ui.py" in turn_entries
    assert not [e for e in turn_entries if e.startswith("src/app/legacy/")]
    assert "src/app/keep.py" in turn_entries


def test_delete_drops_the_path_from_both_manifests(tmp_path, container):
    """
    Given session.context listing docs/notes/scratch.md,
    When a DELETE removes that path,
    Then neither live manifest still lists it.
    """
    # Arrange
    plan_path = _seed_transition(
        tmp_path,
        turn_context="docs/notes/scratch.md\ndocs/notes/keep.md",
        session_context="docs/notes/scratch.md",
    )
    service = container.resolve(ISessionManager)
    report = _report(_log("DELETE", {"path": "docs/notes/scratch.md"}))

    # Act
    next_turn = Path(service.transition_to_next_turn(plan_path, report))

    # Assert
    turn_entries = _entries(next_turn / "turn.context")
    assert "docs/notes/scratch.md" not in turn_entries
    assert "docs/notes/keep.md" in turn_entries

    session_entries = _entries(next_turn.parent / "session.context")
    assert "docs/notes/scratch.md" not in session_entries


def test_recursive_delete_drops_the_subtree_without_over_matching(tmp_path, container):
    """
    Given turn.context listing a directory's contents and a sibling whose name
    merely shares the prefix,
    When a recursive DELETE removes the directory,
    Then every entry beneath it goes and the sibling stays.
    """
    # Arrange
    plan_path = _seed_transition(
        tmp_path,
        turn_context=(
            "src/app/legacy/engine.py\n"
            "src/app/legacy/ui.py\n"
            "src/app/keep.py\n"
            "src/app/legacyish.py"
        ),
    )
    service = container.resolve(ISessionManager)
    report = _report(_log("DELETE", {"path": "src/app/legacy", "recursive": True}))

    # Act
    next_turn = Path(service.transition_to_next_turn(plan_path, report))

    # Assert
    turn_entries = _entries(next_turn / "turn.context")
    assert not [e for e in turn_entries if e.startswith("src/app/legacy/")]
    assert "src/app/keep.py" in turn_entries
    assert "src/app/legacyish.py" in turn_entries


def test_failed_move_leaves_both_manifests_untouched(tmp_path, container):
    """
    Given a MOVE that failed,
    When the turn transitions,
    Then neither manifest is rewritten, because nothing moved.
    """
    # Arrange
    plan_path = _seed_transition(
        tmp_path,
        turn_context="src/app/old_name.py",
        session_context="src/app/old_name.py",
    )
    service = container.resolve(ISessionManager)
    session_context_file = (
        tmp_path / ".teddy" / "sessions" / "manifest-sync" / "session.context"
    )
    before = session_context_file.read_bytes()
    report = _report(
        _log(
            "MOVE",
            {"source": "src/app/old_name.py", "destination": "src/app/new_name.py"},
            status=ActionStatus.FAILURE,
        )
    )

    # Act
    next_turn = Path(service.transition_to_next_turn(plan_path, report))

    # Assert
    assert "src/app/old_name.py" in _entries(next_turn / "turn.context")
    assert session_context_file.read_bytes() == before
