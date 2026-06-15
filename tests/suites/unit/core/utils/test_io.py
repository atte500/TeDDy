"""Tests for the Tee utility class.

This module provides the test infrastructure (fixtures and helpers) for testing
the Tee context manager in io.py, as well as reusable tools for integration
tests that verify history.log creation in SessionOrchestrator.
"""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path
from typing import Iterator

import pytest

from teddy_executor.core.utils.io import Tee


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tee_log_path() -> Iterator[Path]:
    """Create a temporary file path for the Tee log file.

    The file is created in a system temp directory and cleaned up after
    the test completes.
    """
    with tempfile.NamedTemporaryFile(
        suffix=".log", mode="w", encoding="utf-8", delete=False
    ) as f:
        path = Path(f.name)
    yield path
    # Cleanup
    if path.exists():
        path.unlink()


@pytest.fixture
def captured_stdout() -> Iterator[io.StringIO]:
    """Provide a StringIO that temporarily replaces sys.stdout.

    This allows tests to capture what would have been printed to the real
    stdout without side effects.
    """
    original = sys.stdout
    fake = io.StringIO()
    sys.stdout = fake
    yield fake
    sys.stdout = original


@pytest.fixture
def captured_stderr() -> Iterator[io.StringIO]:
    """Provide a StringIO that temporarily replaces sys.stderr.

    This allows tests to capture what would have been printed to the real
    stderr without side effects.
    """
    original = sys.stderr
    fake = io.StringIO()
    sys.stderr = fake
    yield fake
    sys.stderr = original


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def assert_log_contains(log_path: Path, expected: str) -> None:
    """Assert that the log file at *log_path* contains the string *expected*."""
    content = log_path.read_text(encoding="utf-8")
    assert expected in content, (
        f"Expected log to contain:\n  {expected!r}\nActual log content:\n  {content}"
    )


def assert_log_does_not_contain(log_path: Path, unexpected: str) -> None:
    """Assert that the log file at *log_path* does NOT contain *unexpected*."""
    content = log_path.read_text(encoding="utf-8")
    assert unexpected not in content, (
        f"Expected log NOT to contain:\n  {unexpected!r}\n"
        f"Actual log content:\n  {content}"
    )


def assert_tee_restores_streams(tee: Tee) -> None:
    """Assert that after Tee context manager exits, sys.stdout and sys.stderr are restored to their original objects.

    This helper uses the Tee inside a with-block and verifies:
    - Inside the block: streams are replaced
    - After the block: streams are restored to their originals
    """
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    with tee:
        assert sys.stdout is not original_stdout, "Tee should replace sys.stdout"
        assert sys.stderr is not original_stderr, "Tee should replace sys.stderr"

    assert sys.stdout is original_stdout, "sys.stdout not restored after Tee exit"
    assert sys.stderr is original_stderr, "sys.stderr not restored after Tee exit"


# ---------------------------------------------------------------------------
# Tee Unit Tests
# ---------------------------------------------------------------------------


class TestTee:
    """Unit tests for the Tee context manager class."""

    def test_tee_basic_stdout(
        self, tee_log_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify Tee duplicates stdout writes to the log file."""
        test_message = "Hello, stdout!\n"
        with open(tee_log_path, "a", encoding="utf-8") as log_file:
            with Tee(log_file):
                sys.stdout.write(test_message)

        # Original stdout (via capsys) should have the message
        captured = capsys.readouterr()
        assert captured.out == test_message, (
            f"Expected stdout to contain {test_message!r}, got {captured.out!r}"
        )
        # Log file should have the message
        assert_log_contains(tee_log_path, test_message)

    def test_tee_basic_stderr(
        self, tee_log_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify Tee duplicates stderr writes to the log file."""
        test_message = "Hello, stderr!\n"
        with open(tee_log_path, "a", encoding="utf-8") as log_file:
            with Tee(log_file):
                sys.stderr.write(test_message)

        captured = capsys.readouterr()
        assert captured.err == test_message, (
            f"Expected stderr to contain {test_message!r}, got {captured.err!r}"
        )
        assert_log_contains(tee_log_path, test_message)

    def test_tee_flush_propagation(
        self, tee_log_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify that flush() on the Tee writer flushes both original and log file."""
        test_message = "Test flush\n"
        with open(tee_log_path, "a", encoding="utf-8") as log_file:
            with Tee(log_file):
                # Write to sys.stdout (which is the Tee writer) and flush directly
                sys.stdout.write(test_message)
                sys.stdout.flush()

        # After flush, content should be in both
        captured = capsys.readouterr()
        assert captured.out == test_message, (
            f"Expected capsys to contain {test_message!r}, got {captured.out!r}"
        )
        assert_log_contains(tee_log_path, test_message)

    def test_tee_isatty_forwarding(self, tee_log_path: Path) -> None:
        """Verify that isatty() on the Tee writer returns the same as original stdout."""
        original_isatty = sys.stdout.isatty()
        with open(tee_log_path, "a", encoding="utf-8") as log_file:
            with Tee(log_file):
                tee_isatty = sys.stdout.isatty()
        assert tee_isatty == original_isatty, (
            f"Expected isatty() to return {original_isatty}, got {tee_isatty}"
        )

    def test_tee_context_manager_restore(self, tee_log_path: Path) -> None:
        """Verify that sys.stdout and sys.stderr are restored after Tee exits."""
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        with open(tee_log_path, "a", encoding="utf-8") as log_file:
            with Tee(log_file):
                assert sys.stdout is not original_stdout
                assert sys.stderr is not original_stderr

        assert sys.stdout is original_stdout, "sys.stdout not restored"
        assert sys.stderr is original_stderr, "sys.stderr not restored"

    def test_tee_exception_safety_file_open_failure(
        self, tee_log_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify that if the log file cannot be opened, no exception propagates and streams are unchanged."""
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        # Pass None to simulate file open failure (Tee handles None gracefully)
        with Tee(None):
            sys.stdout.write("This should go only to original stdout\n")

        # Streams should be unchanged
        assert sys.stdout is original_stdout, (
            "sys.stdout was modified after file open failure"
        )
        assert sys.stderr is original_stderr, (
            "sys.stderr was modified after file open failure"
        )
        # Original stdout should contain our message (via capsys)
        captured = capsys.readouterr()
        assert captured.out == "This should go only to original stdout\n"
