"""Regression tests for Bug 56 (deliverable 3): the console ask prompt must
propagate Ctrl+C (``KeyboardInterrupt``) instead of silently swallowing it.

``ConsoleAskLoop._pt_prompt`` catches ``(EOFError, KeyboardInterrupt)`` on the
TTY (prompt_toolkit) path and returns an empty string, so pressing Ctrl+C at the
console ask prompt re-prompts silently instead of exiting. The fix keeps the
``EOFError`` swallow (and the non-TTY ``input()`` path) intact while letting
``KeyboardInterrupt`` propagate -- in-session it reaches the session-loop
boundary's clean-exit catch (``session_cli_handlers``), and for the
pre-boundary INITIAL "What are we working on?" prompt the Typer CLI entrypoint
already exits without a traceback.
"""

from typing import cast

import pytest

import teddy_executor.adapters.outbound.console_interactor_ask_loop as ask_loop_module
from teddy_executor.adapters.outbound.console_interactor_ask_loop import (
    ConsoleAskLoop,
)
from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


def _make_loop() -> ConsoleAskLoop:
    """Build a loop for ``_pt_prompt``-only tests.

    ``_pt_prompt`` consults NEITHER constructor dependency, so typed sentinels
    satisfy the constructor without pulling in unrelated fakes or mocks.
    """
    return ConsoleAskLoop(
        cast(ISystemEnvironment, None),
        cast(ConsoleToolingHelper, None),
    )


def _raising(exc_type: type[BaseException]):
    """Return a callable that raises ``exc_type`` when invoked."""

    def _raiser(*_args, **_kwargs):
        raise exc_type()

    return _raiser


@pytest.fixture
def tty(monkeypatch):
    """Force the TTY (prompt_toolkit) branch of ``_pt_prompt``."""
    monkeypatch.setattr(ask_loop_module.sys.stdin, "isatty", lambda: True)


@pytest.fixture
def non_tty(monkeypatch):
    """Force the non-TTY (``input()``) branch of ``_pt_prompt``."""
    monkeypatch.setattr(ask_loop_module.sys.stdin, "isatty", lambda: False)


class TestPtPromptInterruptPropagation:
    """Ctrl+C at the ask prompt must propagate; EOF must remain swallowed."""

    def test_pt_prompt_propagates_keyboard_interrupt_on_tty(self, tty, monkeypatch):
        """A TTY Ctrl+C (ptk_prompt raises KeyboardInterrupt) must propagate."""
        monkeypatch.setattr(ask_loop_module, "ptk_prompt", _raising(KeyboardInterrupt))

        with pytest.raises(KeyboardInterrupt):
            _make_loop()._pt_prompt("Response (type 'e' for editor) > ")

    def test_pt_prompt_preserves_eof_swallow_on_tty(self, tty, monkeypatch):
        """A TTY EOF (ptk_prompt raises EOFError) must still return ``""``."""
        monkeypatch.setattr(ask_loop_module, "ptk_prompt", _raising(EOFError))

        assert _make_loop()._pt_prompt("Response (type 'e' for editor) > ") == ""

    def test_pt_prompt_propagates_keyboard_interrupt_on_non_tty(
        self, non_tty, monkeypatch
    ):
        """On the non-TTY ``input()`` path a KeyboardInterrupt must propagate."""
        monkeypatch.setattr("builtins.input", _raising(KeyboardInterrupt))

        with pytest.raises(KeyboardInterrupt):
            _make_loop()._pt_prompt("Response (type 'e' for editor) > ")

    def test_pt_prompt_preserves_eof_swallow_on_non_tty(self, non_tty, monkeypatch):
        """On the non-TTY ``input()`` path an EOF must still return ``""``."""
        monkeypatch.setattr("builtins.input", _raising(EOFError))

        assert _make_loop()._pt_prompt("Response (type 'e' for editor) > ") == ""
