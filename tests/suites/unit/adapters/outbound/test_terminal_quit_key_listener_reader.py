"""Unit tests: the terminal single-key quit-key reader (Bug 56 bare-`q`).

The concrete ``TerminalQuitKeyListener`` drives the controlling terminal in a
non-canonical mode (VMIN=1, VTIME=0, ISIG KEPT) from a stopped/joined daemon
thread, detects the bare ``q`` key (0x71), and self-delivers SIGINT so the
shared ``InterruptGuard`` runs its already-tested two-phase branch. It is a
no-op off-TTY, backs off while another reader owns stdin, and uses
``msvcrt.kbhit()`` on Windows (no mode change).

This suite drives the reader synchronously via injected fakes -- hand-rolled
in-memory doubles (no dynamic mocks, no global module patching beyond swapping
the platform ``termios``/``msvcrt`` modules).
"""

import os
import signal
import sys
import threading
import time

import pytest

from teddy_executor.adapters.outbound.terminal_quit_key_listener import (
    QUIT_KEY,
    TerminalQuitKeyListener,
)


class _FakeTermios:
    """In-memory stand-in for the POSIX ``termios`` module.

    Models the real 7-slot attr list (``[0]`` iflag, ``[3]`` lflag, ``[6]`` the
    control-character list) so the production save/restore indices are exercised
    faithfully.
    """

    TCSAFLUSH = 2
    ICRNL = 256
    ICANON = 2
    ECHO = 8
    ISIG = 1
    IEXTEN = 1024
    VMIN = 6
    VTIME = 5

    def __init__(self, attrs=None):
        self._attrs = (
            attrs
            if attrs is not None
            else [
                self.ICRNL,
                0,
                0,
                self.ICANON | self.ECHO | self.ISIG | self.IEXTEN,
                0,
                0,
                [0] * 32,
            ]
        )
        self.tcgetattr_calls = []
        self.tcsetattr_calls = []

    def tcgetattr(self, fd):
        self.tcgetattr_calls.append(fd)
        return self._attrs

    def tcsetattr(self, fd, when, attrs):
        self.tcsetattr_calls.append((fd, when, attrs))


class _Recorder:
    """Hand-rolled call recorder (not a mock) counting invocations."""

    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1


class _FakeMsvcrt:
    """In-memory stand-in for the Windows-only ``msvcrt`` module."""

    def __init__(self, keys):
        self._keys = list(keys)

    def kbhit(self):
        return bool(self._keys)

    def getwch(self):
        return self._keys.pop(0)


@pytest.fixture
def fake_termios(monkeypatch):
    """Inject the termios fake so the reader's function-local import sees it."""
    fake = _FakeTermios()
    monkeypatch.setitem(sys.modules, "termios", fake)
    return fake


def _force_posix_tty(monkeypatch, *, isatty=True):
    """Satisfy the reader's POSIX TTY preconditions."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: isatty)
    monkeypatch.setattr(sys.stdin, "fileno", lambda: 0)


_ORIGINAL_LFLAG = (
    _FakeTermios.ICANON | _FakeTermios.ECHO | _FakeTermios.ISIG | _FakeTermios.IEXTEN
)


# --- TTY gate ---


def test_start_is_noop_when_stdin_is_not_a_tty(fake_termios, monkeypatch):
    """Off-TTY the listener must not touch the terminal or spawn a thread."""
    _force_posix_tty(monkeypatch, isatty=False)
    listener = TerminalQuitKeyListener(on_quit=_Recorder())

    listener.start()

    assert fake_termios.tcgetattr_calls == []
    assert fake_termios.tcsetattr_calls == []
    assert listener._thread is None


# --- terminal-mode save/restore discipline ---


def test_enter_noncanonical_mode_keeps_isig_and_sets_vmin_vtime(
    fake_termios, monkeypatch
):
    """The reader must disable ICANON/ECHO while KEEPING ISIG, with VMIN=1/VTIME=0."""
    _force_posix_tty(monkeypatch)
    listener = TerminalQuitKeyListener()

    listener._enter_noncanonical_mode()

    assert fake_termios.tcsetattr_calls, "expected tcsetattr to be called"
    _fd, _when, attrs = fake_termios.tcsetattr_calls[-1]
    assert attrs[3] & _FakeTermios.ISIG, "ISIG must be KEPT so Ctrl+C still works"
    assert not (attrs[3] & _FakeTermios.ICANON), "canonical mode must be disabled"
    assert not (attrs[3] & _FakeTermios.ECHO), "echo must be disabled (no echo)"
    assert attrs[6][_FakeTermios.VMIN] == 1
    assert attrs[6][_FakeTermios.VTIME] == 0


def test_restore_mode_reinstates_the_saved_attrs(fake_termios, monkeypatch):
    """The strict save/restore context must reinstate the original mode."""
    _force_posix_tty(monkeypatch)
    listener = TerminalQuitKeyListener()
    listener._enter_noncanonical_mode()

    listener._restore_mode()

    _fd, _when, restored = fake_termios.tcsetattr_calls[-1]
    assert restored[3] == _ORIGINAL_LFLAG


def test_start_and_stop_manage_mode_and_daemon_thread(fake_termios, monkeypatch):
    """start() enters the mode and runs a daemon thread; stop() restores."""
    _force_posix_tty(monkeypatch)
    listener = TerminalQuitKeyListener()
    monkeypatch.setattr(listener, "_read_loop", lambda: None, raising=False)

    listener.start()
    try:
        assert fake_termios.tcsetattr_calls, "start() must enter non-canonical mode"
        assert listener._thread is not None
        assert listener._thread.daemon is True
    finally:
        listener.stop()

    assert fake_termios.tcsetattr_calls[-1][2][3] == _ORIGINAL_LFLAG


# --- byte detection ---


def test_process_byte_triggers_on_the_quit_key():
    """Detecting 0x71 must trigger the quit hook."""
    recorder = _Recorder()
    listener = TerminalQuitKeyListener(on_quit=recorder)

    assert listener._process_byte(QUIT_KEY) is True
    assert recorder.calls == 1


def test_process_byte_ignores_non_quit_bytes():
    """Any other byte must not trigger the quit hook."""
    recorder = _Recorder()
    listener = TerminalQuitKeyListener(on_quit=recorder)

    assert listener._process_byte(0x61) is False
    assert recorder.calls == 0


# --- self-delivery ---


def test_read_loop_self_delivers_sigint_on_quit_key(monkeypatch):
    """With no injected hook the reader self-delivers SIGINT to the process."""
    listener = TerminalQuitKeyListener()  # on_quit defaults to None -> self-deliver
    monkeypatch.setattr(listener, "_read_one_byte", lambda: QUIT_KEY, raising=False)
    delivered = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: delivered.append((pid, sig)))

    listener._read_loop()

    assert delivered == [(os.getpid(), signal.SIGINT)]


def test_trigger_invokes_injected_on_quit_instead_of_self_delivering(monkeypatch):
    """An injected on_quit hook is used; SIGINT is NOT self-delivered."""
    recorder = _Recorder()
    listener = TerminalQuitKeyListener(on_quit=recorder)
    delivered = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: delivered.append((pid, sig)))

    listener._trigger()

    assert recorder.calls == 1
    assert delivered == []


# --- prompt-pause ---


def test_read_loop_does_not_consume_while_stdin_is_owned(monkeypatch):
    """While stdin is owned by another reader the loop must not consume bytes."""
    from teddy_executor.core.utils.stdin_ownership import stdin_owned

    listener = TerminalQuitKeyListener(on_quit=_Recorder())
    reads = []
    monkeypatch.setattr(
        listener, "_read_one_byte", lambda: reads.append(1) or None, raising=False
    )
    exited = []

    with stdin_owned():
        thread = threading.Thread(
            target=lambda: (listener._read_loop(), exited.append("exited")),
            daemon=True,
        )
        thread.start()
        time.sleep(0.2)
        listener._stop_event.set()
        thread.join(timeout=2.0)

    assert reads == [], "the reader must not consume bytes while stdin is owned"
    assert exited == ["exited"], "the reader loop must terminate when stopped"


# --- Windows path ---


def test_windows_mode_does_not_change_termios(fake_termios, monkeypatch):
    """On Windows the reader must not perform any termios mode change."""
    monkeypatch.setattr(sys, "platform", "win32")
    listener = TerminalQuitKeyListener()

    listener._enter_noncanonical_mode()

    assert fake_termios.tcgetattr_calls == []
    assert fake_termios.tcsetattr_calls == []


def test_windows_read_one_byte_uses_msvcrt(monkeypatch):
    """On Windows the byte source is msvcrt.kbhit/getwch (no mode change)."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "msvcrt", _FakeMsvcrt(["q"]))
    listener = TerminalQuitKeyListener()

    assert listener._read_one_byte() == QUIT_KEY
