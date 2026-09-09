"""Regression tests for Bug 48: spawn_editor must not fail when sys.stdin lacks fileno.

In Textual's TUI, sys.stdin is replaced by a custom wrapper that raises
AttributeError on fileno(). This test verifies that spawn_editor() catches
AttributeError gracefully (or avoids it entirely by not passing stdin
explicitly).
"""

import os
import sys
import tempfile
from unittest.mock import patch


# Import the production module
from teddy_executor.adapters.inbound.textual_plan_reviewer_editor import spawn_editor


class DummyStdinNoFileno:
    """Mimics Textual's stdin wrapper that lacks fileno()."""

    def isatty(self):
        return False

    @property
    def name(self):
        return "<stdin>"

    def fileno(self):
        raise AttributeError("DummyStdin has no fileno")


def test_spawn_editor_no_attribute_error_when_stdin_lacks_fileno():
    """spawn_editor must not raise AttributeError when sys.stdin lacks fileno().

    Regression test for Bug 48. The fix removes explicit stdin=sys.stdin
    from the Popen call, so fileno() is never called on sys.stdin.
    """
    original_stdin = sys.stdin

    try:
        sys.stdin = DummyStdinNoFileno()

        # Create a temp file to pass to spawn_editor
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            temp_path = f.name

        try:
            # Mock subprocess.Popen to avoid actually spawning anything
            with patch("subprocess.Popen") as mock_popen:
                # This should NOT raise an AttributeError
                import pytest

                try:
                    spawn_editor(["nonexistent_editor_12345"], temp_path)
                except AttributeError as e:
                    pytest.fail(f"spawn_editor raised AttributeError unexpectedly: {e}")
                except Exception:
                    # Non-AttributeError exceptions (FileNotFoundError, etc.)
                    # are acceptable since we're passing a dummy command.
                    # The important thing is that fileno() was not called.
                    pass

                # Verify Popen was called without stdin/stdout/stderr kwargs
                if mock_popen.called:
                    call_kwargs = mock_popen.call_args[1]
                    assert "stdin" not in call_kwargs, (
                        f"Popen should not receive stdin kwarg, got: {call_kwargs}"
                    )
                    assert "stdout" not in call_kwargs, (
                        f"Popen should not receive stdout kwarg, got: {call_kwargs}"
                    )
                    assert "stderr" not in call_kwargs, (
                        f"Popen should not receive stderr kwarg, got: {call_kwargs}"
                    )
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    finally:
        sys.stdin = original_stdin
