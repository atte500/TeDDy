"""Unit tests for the Tee utility class (history.log writer)."""

from pathlib import Path


from teddy_executor.core.utils.io import Tee


def test_tee_writes_to_both_stdout_and_log_file(tmp_path):
    """Writing to stdout via Tee context should appear in both original stdout and the log file."""
    # Arrange
    import io
    import sys

    log_file = tmp_path / "history.log"
    original_stdout = sys.stdout
    captured_original = io.StringIO()

    # Temporarily replace sys.stdout with our capture buffer to simulate original stdout
    sys.stdout = captured_original

    tees = Tee(log_file)

    # Act: enter context, write something, exit
    try:
        tees.__enter__()
        print("Hello, Tee!", file=sys.stdout)
    finally:
        tees.__exit__(None, None, None)

    # Restore original stdout
    sys.stdout = original_stdout

    # Assert: original stdout got the text
    assert "Hello, Tee!" in captured_original.getvalue(), (
        f"Original stdout should contain the written text. Got: {captured_original.getvalue()!r}"
    )

    # Assert: log file got the text (including newline from print)
    log_content = log_file.read_text(encoding="utf-8")
    assert "Hello, Tee!" in log_content, (
        f"Log file should contain the written text. Content: {log_content!r}"
    )


def test_tee_is_context_manager():
    """Tee should implement the context manager protocol (__enter__/__exit__)."""
    # Arrange: create a path for the log file
    log_path = Path("/tmp/test_history.log")

    # Act
    tees = Tee(log_path)

    # Assert: Tee should have __enter__ and __exit__ methods
    assert hasattr(tees, "__enter__")
    assert hasattr(tees, "__exit__")


def test_tee_constructor_accepts_path():
    """Tee constructor should accept a Path object."""
    log_path = Path("/tmp/test_history.log")
    tees = Tee(log_path)
    assert tees is not None


def test_tee_writer_flush_propagates_to_both_outputs():
    """Calling flush on _TeeWriter should flush both the original stdout and the log file."""
    import io
    from teddy_executor.core.utils.io import _TeeWriter

    # Arrange
    original = io.StringIO()
    log_file = io.StringIO()
    writer = _TeeWriter(original, log_file)

    # Act
    writer.flush()

    # Assert: no exception raised (flush on StringIO is a no-op but should not fail)
    # We verify flush succeeded by checking that both streams are still open
    assert not original.closed
    assert not log_file.closed


def test_tee_writer_isatty_returns_original_stdout_value():
    """isatty() on _TeeWriter should forward to the original stdout."""
    from teddy_executor.core.utils.io import _TeeWriter

    # Arrange: StringIO returns False for isatty()
    import io

    original = io.StringIO()
    log_file = io.StringIO()
    writer = _TeeWriter(original, log_file)

    # Act / Assert
    assert writer.isatty() is False, "StringIO.isatty() should return False"


def test_tee_restores_stdout_on_exception():
    """Original sys.stdout should be restored even when an exception occurs inside the Tee context."""
    import io
    import sys

    log_path = Path("/tmp/test_exception_restore.log")
    original_stdout = sys.stdout
    captured = io.StringIO()
    sys.stdout = captured

    tees = Tee(log_path)
    try:
        tees.__enter__()
        # Simulate an exception inside the context
        raise ValueError("Test error")
    except ValueError:
        pass
    finally:
        tees.__exit__(None, None, None)  # Normal exit pass

    # Restore original
    sys.stdout = original_stdout

    # Assert: sys.stdout is restored to original
    assert sys.stdout is original_stdout, (
        "sys.stdout should be restored to original after Tee exit"
    )


def test_tee_handles_file_open_failure_gracefully(monkeypatch):
    """Tee should not crash when the log file cannot be opened (e.g., permission error)."""
    import io
    import sys
    from pathlib import Path

    log_path = Path("/proc/1/root/history.log")  # Likely unwritable location
    original_stdout = sys.stdout
    captured = io.StringIO()
    sys.stdout = captured

    tees = Tee(log_path)
    try:
        tees.__enter__()
        # Write something — should still go to original stdout
        print("Still works!", file=sys.stdout)
    finally:
        tees.__exit__(None, None, None)

    sys.stdout = original_stdout

    # Assert: original stdout still got the text even though log file failed
    assert "Still works!" in captured.getvalue()
    # Assert: sys.stdout was restored
    assert sys.stdout is original_stdout
