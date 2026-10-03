"""Regression tests: the terminal quit-key reader must back off from stdin that
becomes readable while another reader owns it.

The reader consumes stdin one byte at a time from a background thread. It once
tested stdin ownership only BEFORE blocking in ``select()`` (POSIX) / ``kbhit()``
(Windows). A byte that arrives AFTER a console prompt claims stdin -- e.g.
prompt_toolkit's cursor-position reply -- could therefore be stolen in that
check-then-read window, corrupting the owner's input. These tests pin the
observable contract at that seam: while stdin is owned, a readable byte is left
untouched for its owner.

POSIX is exercised through a real pipe (``select`` works on pipes); Windows
through an in-memory ``msvcrt`` double (no dynamic mocks, consistent with the
sibling reader suite).
"""

import os
import sys

import pytest

from teddy_executor.adapters.outbound.terminal_quit_key_listener import (
    TerminalQuitKeyListener,
)
from teddy_executor.core.utils.stdin_ownership import stdin_owned


@pytest.mark.skipif(
    sys.platform == "win32", reason="exercises the POSIX select/read path"
)
def test_reader_leaves_readable_byte_for_owner_on_posix(monkeypatch):
    """While stdin is owned, a byte that is already readable must NOT be consumed."""
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b"\x1b")
        monkeypatch.setattr(sys.stdin, "fileno", lambda: read_fd)
        listener = TerminalQuitKeyListener()

        with stdin_owned():
            consumed = listener._read_one_byte()

        assert consumed is None, "reader must back off while stdin is owned"
        # The owner's byte must still be waiting on stdin, intact.
        assert os.read(read_fd, 1) == b"\x1b"
    finally:
        os.close(read_fd)
        os.close(write_fd)


@pytest.mark.skipif(
    sys.platform == "win32", reason="exercises the POSIX select/read path"
)
def test_reader_consumes_readable_byte_when_unowned_on_posix(monkeypatch):
    """Positive control: with no owner, the readable byte is consumed normally."""
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b"\x1b")
        monkeypatch.setattr(sys.stdin, "fileno", lambda: read_fd)
        listener = TerminalQuitKeyListener()

        assert listener._read_one_byte() == 0x1B
    finally:
        os.close(read_fd)
        os.close(write_fd)


class _FakeMsvcrt:
    """In-memory stand-in for the Windows-only ``msvcrt`` module."""

    def __init__(self):
        self.keys_read = []

    def kbhit(self):
        return True

    def getwch(self):
        self.keys_read.append("q")
        return "q"


def test_reader_leaves_key_for_owner_on_windows(monkeypatch):
    """On Windows the reader must not call getwch() while stdin is owned."""
    monkeypatch.setattr(sys, "platform", "win32")
    fake_msvcrt = _FakeMsvcrt()
    monkeypatch.setitem(sys.modules, "msvcrt", fake_msvcrt)
    listener = TerminalQuitKeyListener()

    with stdin_owned():
        consumed = listener._read_one_byte()

    assert consumed is None, "reader must back off while stdin is owned"
    assert fake_msvcrt.keys_read == [], "getwch() must not be called while owned"
