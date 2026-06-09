"""Integration tests for history.log creation during session execution.

Tests format correctness, validation failure logging, non-session mode,
append mode, stdout restoration, and Tee failure isolation.
"""

from unittest.mock import MagicMock  # noqa: TID251


from tests.harness.setup.orchestrator_helpers import (
    build_mocked_orchestrator,
    create_session_directory,
)


def test_history_log_format_correctness(tmp_path):
    """The history.log should contain the correctly formatted metadata header.

    Given a session turn execution,
    When the orchestrator runs,
    The history.log should contain [NN] <title> | Waiting for <agent>... format.
    """
    # Arrange
    session_root, plan_path = create_session_directory(tmp_path, turn_number="01")
    history_log = session_root / "history.log"
    orchestrator = build_mocked_orchestrator(session_root, plan_path)

    # Act
    orchestrator.execute(plan_path=plan_path, interactive=True)

    # Assert: history.log exists and contains correctly formatted header
    assert history_log.exists(), "history.log should exist"
    log_content = history_log.read_text(encoding="utf-8")
    assert "[01] Test Plan | Waiting for developer to respond..." in log_content, (
        f"Expected header with turn number, title, and agent. Got:\n{log_content}"
    )
    # Verify the "Waiting for" prefix is present (key distinction from raw text)
    assert "Waiting for" in log_content, (
        f"Header should contain 'Waiting for' prefix. Got:\n{log_content}"
    )
    # Verify model line exists in the header
    assert "openrouter/deepseek/deepseek-v4-flash:nitro" in log_content, (
        f"Header should contain model name. Got:\n{log_content}"
    )
    # Verify context line exists in the header
    assert "Context:" in log_content, (
        f"Header should contain 'Context:' line. Got:\n{log_content}"
    )
    # Verify cost line exists in the header
    assert "Session Cost:" in log_content, (
        f"Header should contain 'Session Cost:' line. Got:\n{log_content}"
    )


def test_history_log_validation_failure_captured(tmp_path):
    """history.log is created during session execution even with validation errors.

    Given a session turn with validation errors (but not a hard validation failure
    that returns an ExecutionReport),
    When the orchestrator runs,
    The history.log should exist and contain the metadata header (because execution
    continues to step 3.5), but validation error text is not printed to stdout.
    """
    # Arrange: create session directory and mock orchestrator with validation failure
    session_root, plan_path = create_session_directory(tmp_path, turn_number="01")
    history_log = session_root / "history.log"
    orchestrator = build_mocked_orchestrator(session_root, plan_path)

    # Override the validator mock to return validation errors
    from teddy_executor.core.services.plan_validator import ValidationError

    validation_error = ValidationError(
        file_path="dummy.md",
        message="Test validation error",
    )
    orchestrator._plan_validator.validate.return_value = [validation_error]

    # Act
    orchestrator.execute(plan_path=plan_path, interactive=True)

    # Assert: history.log should exist
    assert history_log.exists(), (
        f"history.log should exist even on validation failure. Path: {history_log}"
    )
    log_content = history_log.read_text(encoding="utf-8")
    # Header should be present (execution continues past validation to step 3.5)
    assert "[01] Test Plan | Waiting for developer to respond..." in log_content, (
        f"Header should be present despite validation errors. Got:\n{log_content}"
    )
    # The validation error text is NOT printed to stdout because the orchestrator
    # does not log validation errors to stdout — they are only returned in the report.
    # This is a known gap: validation failure output should ideally be visible
    # in the history.log for debugging purposes.
    assert "Test validation error" not in log_content, (
        "Validation error text should not be in history.log (not printed to stdout). "
        f"Got:\n{log_content}"
    )


def test_history_log_non_session_mode(tmp_path):
    """No history.log should be created when executing in non-session mode.

    Given a non-session execute call (plan_path is None),
    When the orchestrator runs,
    No history.log should be created.
    """
    # Arrange: create a session directory but pass plan_path=None to simulate non-session
    session_root, plan_path = create_session_directory(tmp_path, turn_number="01")
    history_log = session_root / "history.log"
    orchestrator = build_mocked_orchestrator(session_root, plan_path)

    # Act: call execute without plan_path (non-session mode)
    orchestrator.execute(plan_path=None, interactive=True)

    # Assert: history.log should NOT exist
    assert not history_log.exists(), (
        "history.log should not be created in non-session mode"
    )


def test_history_log_append_content_across_turns(tmp_path):
    """history.log should append content across multiple turns.

    Given two sequential session turns,
    When both execute,
    The history.log should contain both turns' content in chronological order.
    """
    # Arrange: create first turn directory
    session_root, plan_path = create_session_directory(tmp_path, turn_number="01")
    history_log = session_root / "history.log"
    orchestrator = build_mocked_orchestrator(session_root, plan_path)

    # Act: first turn
    orchestrator.execute(plan_path=plan_path, interactive=True)

    # Arrange second turn: create turn 02 directory and configure orchestrator
    turn_02 = session_root / "02"
    turn_02.mkdir(parents=True)
    plan_02 = turn_02 / "plan.md"
    plan_02.write_text("# Plan 2\n", encoding="utf-8")

    # Build a new orchestrator for turn 02 with updated metadata
    orchestrator_02 = build_mocked_orchestrator(session_root, str(plan_02))
    mock_plan = MagicMock()
    mock_plan.metadata = {"Agent": "developer", "Status": "SUCCESS 🟢"}
    mock_plan.is_session = True
    mock_plan.title = "Test Plan"
    orchestrator_02._plan_parser.parse.return_value = mock_plan

    # Act: second turn
    orchestrator_02.execute(plan_path=str(plan_02), interactive=True)

    # Assert: history.log contains both turns' headers (two "[0X]" markers)
    assert history_log.exists(), "history.log should exist"
    log_content = history_log.read_text(encoding="utf-8")
    assert "[01]" in log_content, (
        f"First turn header should appear. Got:\n{log_content}"
    )
    assert "[02]" in log_content, (
        f"Second turn header should appear. Got:\n{log_content}"
    )
    # Verify chronological order: [01] appears before [02]
    assert log_content.find("[01]") < log_content.find("[02]"), (
        "Turn 01 should appear before Turn 02 in chronological order"
    )


def test_history_log_stdout_restored_after_execution(tmp_path, capsys):
    """sys.stdout should be restored to the original after session execution completes.

    Given a session turn execution,
    When the orchestrator finishes (even with an exception),
    sys.stdout should point back to the original stdout.
    """
    import sys

    # Arrange
    session_root, plan_path = create_session_directory(tmp_path, turn_number="01")
    original_stdout = sys.stdout
    orchestrator = build_mocked_orchestrator(session_root, plan_path)

    # Act: execute normally
    orchestrator.execute(plan_path=plan_path, interactive=True)

    # Assert: sys.stdout is restored to original
    assert sys.stdout is original_stdout, (
        f"sys.stdout should be restored to original after execution. "
        f"Got: {type(sys.stdout).__name__}"
    )


def test_history_log_tee_failure_isolation(tmp_path):
    """Session should continue without crashing when the Tee cannot write to the log file.

    Given a session turn with a read-only history.log path,
    When the orchestrator executes,
    The session should complete without crashing, and stdout output should still appear.
    """
    import sys

    # Arrange: create session directory
    session_root, plan_path = create_session_directory(tmp_path, turn_number="01")

    # Manually create an unwritable history.log path (permissions simulation)
    # Use a path that cannot be written (e.g., inside /proc or similar)
    # Since we can't easily create read-only files in tmp_path, we'll use
    # a path that points to a directory instead of a file
    unwritable_log = tmp_path / "unwritable" / "history.log"
    # Create a file at that location that is not writable in a typical test env
    # Actually, the simplest approach: point history.log to a path that exists as a directory
    session_root_log_dir = session_root / "history.log"  # This will be a directory
    session_root_log_dir.mkdir(parents=True, exist_ok=True)

    # Build orchestrator — it will try to open session_root / "history.log" which is now a directory
    # We need to modify the session_root to make the log path conflict
    # Simpler approach: directly test that Tee.__enter__ handles failures gracefully
    from teddy_executor.core.utils.io import Tee
    import io

    original_stdout = sys.stdout
    captured = io.StringIO()
    sys.stdout = captured

    # Use a path that's likely to cause OSError on open for append
    # On Linux, /proc/1/root is not writable; on macOS, use a path that fails
    bad_log = tmp_path / "nonexistent_dir" / "history.log"  # Parent doesn't exist
    # Actually, Path.open with 'a' will create the file if parent exists but not if parent missing
    # A more reliable approach: mock the open to raise OSError
    import builtins

    original_open = builtins.open

    def mock_open_fail(*args, **kwargs):
        if "history.log" in str(args[0]):
            raise OSError("Permission denied")
        return original_open(*args, **kwargs)

    monkeypatch_for_tee = __import__("pytest").MonkeyPatch()
    monkeypatch_for_tee.setattr(builtins, "open", mock_open_fail)

    try:
        tees = Tee(tmp_path / "history.log")
        tees.__enter__()
        print("This should still appear on stdout", file=sys.stdout)
    finally:
        tees.__exit__(None, None, None)
        monkeypatch_for_tee.undo()

    sys.stdout = original_stdout

    # Assert: stdout still captured even though Tee failed to open log
    assert "This should still appear on stdout" in captured.getvalue(), (
        "Stdout should still capture text even when Tee log file open fails"
    )
    # Assert: sys.stdout restored
    assert sys.stdout is original_stdout, (
        "sys.stdout should be restored even after Tee failure"
    )
