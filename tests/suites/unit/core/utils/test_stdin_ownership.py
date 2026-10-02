"""Contract tests: the process-global stdin-ownership guard (Bug 56 bare-`q`).

The quit-key reader must not consume bytes while another reader (the console
ask prompt, the external editor) owns stdin. The ownership guard is a
process-global primitive: a ``stdin_owned()`` context manager claims stdin for
the duration of the block and ``is_stdin_owned()`` reports it. This mirrors the
accepted process-global treatment of the signal-disposition and terminal-mode
concerns (stdlib-only, no DI framework).
"""

import pytest

from teddy_executor.core.utils.stdin_ownership import is_stdin_owned, stdin_owned


def test_stdin_is_unowned_by_default():
    """Nothing owns stdin until a claim is made."""
    assert is_stdin_owned() is False


def test_stdin_owned_claims_then_releases():
    """The context manager claims stdin on entry and releases it on exit."""
    with stdin_owned():
        assert is_stdin_owned() is True
    assert is_stdin_owned() is False


def test_stdin_owned_releases_on_exception():
    """Ownership is released even when the block raises."""
    with pytest.raises(RuntimeError):
        with stdin_owned():
            assert is_stdin_owned() is True
            raise RuntimeError("boom")
    assert is_stdin_owned() is False
