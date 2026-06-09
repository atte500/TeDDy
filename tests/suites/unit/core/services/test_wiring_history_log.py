"""Wiring tests for history.log creation during session execution."""

from tests.harness.setup.orchestrator_helpers import (
    build_mocked_orchestrator,
    create_session_directory,
)


def test_history_log_created_in_session_mode(tmp_path, capsys):
    """History.log should be created with stdout content when executing in session mode.

    This tests the Tee installation: the Tee wraps sys.stdout before the metadata
    header is printed, so both stdout and history.log should contain identical content.
    """
    # Arrange: create a real session directory structure for the Tee to write to
    session_root, plan_path = create_session_directory(tmp_path)
    history_log = session_root / "history.log"

    # Build orchestrator with all mocks
    orchestrator = build_mocked_orchestrator(session_root, plan_path)

    # Act
    orchestrator.execute(plan_path=plan_path, interactive=True)

    # Assert: history.log should exist
    assert history_log.exists(), (
        f"Expected history.log at {history_log} but file was not created"
    )

    # Assert: history.log should contain the metadata header lines
    log_content = history_log.read_text(encoding="utf-8")
    assert "[01] Test Plan | Waiting for developer to respond..." in log_content, (
        f"Expected header line in history.log. Content:\n{log_content}"
    )

    # Assert: non-session mode does not create history.log
    non_session_history = tmp_path / "non-session" / "history.log"
    assert not non_session_history.exists(), (
        "Non-session mode should not create history.log"
    )
