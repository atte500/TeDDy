"""Regression tests for the TTY guards in the shared cooked-mode restore.

The restore helper must run its ``tcsetattr`` flush only on a real TTY and
never during a test run, so an accidental restore cannot hang a worker. A
hand-built ``termios`` fake records the calls, because the project bans bare
``unittest.mock`` objects and a dynamic mock cannot model the module's plain
constants.
"""

import sys
from types import SimpleNamespace

import pytest

from teddy_executor.adapters.outbound.console_interactor_helpers import (
    restore_terminal_mode,
)
from teddy_executor.adapters.outbound.system_environment_adapter import (
    SystemEnvironmentAdapter,
)


@pytest.fixture
def fake_termios(monkeypatch):
    """Install a recording ``termios`` fake so the function-local import sees it."""
    calls = []
    fake = SimpleNamespace(
        TCSAFLUSH=2,
        ICRNL=256,
        ICANON=2,
        ECHO=8,
        ISIG=1,
        IEXTEN=1024,
        tcgetattr=lambda _fd: [0] * 7,
        tcsetattr=lambda fd, when, attrs: calls.append((fd, when, attrs)),
        tcsetattr_calls=calls,
    )
    monkeypatch.setitem(sys.modules, "termios", fake)
    return fake


@pytest.fixture
def tty_stdin(monkeypatch):
    """Pretend stdin is a TTY on descriptor 0 and mute the shell-out."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdin, "fileno", lambda: 0)
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: None)
    monkeypatch.setattr("sys.platform", "linux")


def test_system_environment_adapter_run_command_guards_tty(
    monkeypatch, fake_termios, tty_stdin
):
    """run_command restores the terminal only outside a test run."""
    adapter = SystemEnvironmentAdapter()

    # PART 1: without the test marker, the restore path runs tcsetattr.
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    adapter.run_command(["ls"])
    assert fake_termios.tcsetattr_calls, "Test Setup Error: tcsetattr was NOT called."

    # PART 2: the test marker short-circuits the restore.
    fake_termios.tcsetattr_calls.clear()
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_tty_guards")
    adapter.run_command(["ls"])
    assert not fake_termios.tcsetattr_calls, (
        "VULNERABILITY DETECTED: SystemEnvironmentAdapter.run_command "
        "attempted tcsetattr during a test run."
    )


def test_restore_terminal_mode_guards_tty(monkeypatch, fake_termios, tty_stdin):
    """restore_terminal_mode restores the terminal only outside a test run."""
    # PART 1: without the test marker, the restore path runs tcsetattr.
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    restore_terminal_mode()
    assert fake_termios.tcsetattr_calls, "Test Setup Error: tcsetattr was NOT called."

    # PART 2: the test marker short-circuits the restore.
    fake_termios.tcsetattr_calls.clear()
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_tty_guards")
    restore_terminal_mode()
    assert not fake_termios.tcsetattr_calls, (
        "VULNERABILITY DETECTED: restore_terminal_mode "
        "attempted tcsetattr during a test run."
    )
