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
