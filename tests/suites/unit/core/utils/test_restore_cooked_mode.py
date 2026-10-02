"""Regression tests for Bug 56 (deliverable 4): the cooked-mode restore
concern must have a SINGLE source of truth.

The "re-enable the terminal's cooked mode after an external editor exits in
raw mode" logic was duplicated across three adapter sites, two of which
historically forgot to re-enable ``ISIG | IEXTEN`` (Bug 56 C1), so the terminal
stopped GENERATING SIGINT. The Poka-Yoke fix extracts one TTY-guarded helper --
always setting ``ICANON | ECHO | ISIG | IEXTEN | ICRNL`` -- and routes every
consumer through it so a future restore site cannot re-introduce the omission.

This suite pins:
  (a) the shared helper's flag mask and its not-a-TTY no-op (fake termios), and
  (b) that each of the three consumers delegates to the shared helper.

The endpoint flag values at the TUI-editor and system-environment sites remain
pinned by the sibling ``test_terminal_cooked_mode_restore`` suite; this suite
adds the helper-level / delegation structure WITHOUT duplicating those pins.
"""

import sys

import pytest


class _FakeTermios:
    """Hand-rolled in-memory stand-in for the POSIX ``termios`` module."""

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
    """Inject the termios fake for the helper's function-local import."""
    fake = _FakeTermios()
    monkeypatch.setitem(sys.modules, "termios", fake)
    return fake


def _force_restore_preconditions(monkeypatch, *, isatty: bool) -> None:
    """Satisfy the shared helper's guard so it reaches the termios path.

    IMPORTANT: call this from INSIDE the test body (the *call* phase), NOT from a
    fixture. pytest re-sets ``PYTEST_CURRENT_TEST`` immediately before invoking
    the test function -- AFTER fixtures have run -- so a fixture-level
    ``monkeypatch.delenv`` is silently undone and the helper's
    ``"PYTEST_CURRENT_TEST" in os.environ`` guard short-circuits (confirmed by
    ``spikes/debug/test_56_restore_flag_diag.py``: the fixture variant saw
    ``PYTEST_CURRENT_TEST in os.environ == True`` and never called ``tcsetattr``,
    while the inline variant saw ``False`` and recorded the full cooked-mode
    mask ``[256, 0, 0, 1035, 0, 0, 0]``).
    """
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: isatty)
    monkeypatch.setattr(sys.stdin, "fileno", lambda: 0)


def test_shared_helper_sets_full_cooked_mode_flags(fake_termios, monkeypatch):
    """The single helper must re-enable ICRNL + ICANON | ECHO | ISIG | IEXTEN."""
    from teddy_executor.core.utils.terminal import restore_cooked_mode

    _force_restore_preconditions(monkeypatch, isatty=True)

    restore_cooked_mode()

    assert fake_termios.tcsetattr_calls, "helper did not call tcsetattr"
    _fd, _when, attrs = fake_termios.tcsetattr_calls[-1]
    assert attrs[0] & fake_termios.ICRNL, "helper must set ICRNL"
    assert attrs[3] & fake_termios.ICANON, "helper must set ICANON"
    assert attrs[3] & fake_termios.ECHO, "helper must set ECHO"
    assert attrs[3] & fake_termios.ISIG, "helper must set ISIG (Ctrl+C)"
    assert attrs[3] & fake_termios.IEXTEN, "helper must set IEXTEN"


def test_shared_helper_is_noop_when_not_a_tty(fake_termios, monkeypatch):
    """The helper must not touch a non-TTY stdin (guard)."""
    from teddy_executor.core.utils.terminal import restore_cooked_mode

    _force_restore_preconditions(monkeypatch, isatty=False)

    restore_cooked_mode()

    assert fake_termios.tcsetattr_calls == [], "helper must gate on isatty()"


class _Recorder:
    """Hand-rolled call recorder (not a mock) counting invocations."""

    def __init__(self):
        self.calls = 0

    def __call__(self, *_args, **_kwargs):
        self.calls += 1


def test_tui_editor_restore_delegates_to_shared_helper(monkeypatch):
    """The TUI editor's cooked-mode restore must route through the shared helper."""
    import teddy_executor.adapters.inbound.textual_plan_reviewer_editor as mod

    rec = _Recorder()
    monkeypatch.setattr(mod, "restore_cooked_mode", rec)

    mod._restore_terminal_cooked_mode()

    assert rec.calls == 1, "TUI editor restore must delegate to the shared helper"


def test_console_helper_delegates_to_shared_helper(monkeypatch):
    """``console_interactor_helpers.restore_terminal_mode`` must delegate."""
    import teddy_executor.adapters.outbound.console_interactor_helpers as mod

    rec = _Recorder()
    monkeypatch.setattr(mod, "restore_cooked_mode", rec)

    mod.restore_terminal_mode()

    assert rec.calls == 1, "console helper must delegate to the shared helper"


def test_system_environment_run_command_delegates_to_shared_helper(monkeypatch):
    """``SystemEnvironmentAdapter.run_command``'s finally must delegate."""
    import teddy_executor.adapters.outbound.system_environment_adapter as mod

    rec = _Recorder()
    monkeypatch.setattr(mod, "restore_cooked_mode", rec)
    monkeypatch.setattr("subprocess.run", lambda *_a, **_k: None)

    mod.SystemEnvironmentAdapter().run_command(["true"])

    assert rec.calls == 1, "run_command finally must delegate to the shared helper"
