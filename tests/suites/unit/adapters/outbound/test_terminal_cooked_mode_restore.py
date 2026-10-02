"""Regression tests for Bug 56 (C1): cooked-mode restore must re-enable
SIGINT generation flags.

After an external editor (vim/nvim) exits in raw mode, the terminal may be
left with ISIG/IEXTEN cleared, so Ctrl+C no longer GENERATES SIGINT. The
cooked-mode restore helpers must therefore re-enable ISIG | IEXTEN, not just
ICANON | ECHO.

This suite asserts the flag VALUES passed to tcsetattr at BOTH restore sites,
parametrized over the two sites. The existing test_tty_guards suite only
asserts WHETHER tcsetattr is called (guard behavior), not the flags it sets.
"""

import sys

import pytest


class _FakeTermios:
    """Minimal in-memory stand-in for the POSIX ``termios`` module.

    Records ``tcsetattr`` calls so tests can assert the exact lflag bits the
    production restore sites set. A hand-rolled fake (real constants + real
    recorded state) is used instead of a dynamic mock.
    """

    TCSAFLUSH = 2
    ICRNL = 256
    ICANON = 2
    ECHO = 8
    ISIG = 1
    IEXTEN = 1024

    def __init__(self):
        self.tcsetattr_calls = []

    def tcgetattr(self, *_args):
        return [0] * 7

    def tcsetattr(self, fd, when, attrs):
        self.tcsetattr_calls.append((fd, when, list(attrs)))


@pytest.fixture
def fake_termios(monkeypatch):
    """Inject the termios fake so the production function-local import sees it."""
    fake = _FakeTermios()
    monkeypatch.setitem(sys.modules, "termios", fake)
    return fake


def _restore_via_tui_editor() -> None:
    """Site 1: TUI plan reviewer suspend-cycle cooked-mode restore."""
    from teddy_executor.adapters.inbound.textual_plan_reviewer_editor import (
        _restore_terminal_cooked_mode,
    )

    _restore_terminal_cooked_mode()


def _restore_via_system_environment() -> None:
    """Site 2: SystemEnvironmentAdapter.run_command emergency TTY restore."""
    from teddy_executor.adapters.outbound.system_environment_adapter import (
        SystemEnvironmentAdapter,
    )

    SystemEnvironmentAdapter().run_command(["true"])


@pytest.mark.parametrize(
    "invoke_restore",
    [_restore_via_tui_editor, _restore_via_system_environment],
    ids=["tui_editor_suspend_restore", "system_environment_run_command"],
)
def test_restore_re_enables_isig_and_iexten(invoke_restore, fake_termios, monkeypatch):
    """Both cooked-mode restore sites must re-enable ISIG | IEXTEN.

    Without ISIG the terminal stops generating SIGINT on Ctrl+C; without
    IEXTEN extended input processing is lost. Both must be restored so the
    terminal returns to a true cooked mode after an editor exits in raw mode.
    """
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdin, "fileno", lambda: 0)
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: None)

    invoke_restore()

    assert fake_termios.tcsetattr_calls, (
        "restore did not call tcsetattr; the site was not exercised"
    )
    _fd, _when, attrs = fake_termios.tcsetattr_calls[-1]
    lflag = attrs[3]
    assert lflag & fake_termios.ISIG, (
        "restore must re-enable termios.ISIG so Ctrl+C GENERATES SIGINT"
    )
    assert lflag & fake_termios.IEXTEN, (
        "restore must re-enable termios.IEXTEN to match cooked mode"
    )
