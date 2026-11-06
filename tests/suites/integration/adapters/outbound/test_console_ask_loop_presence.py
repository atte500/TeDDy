"""Integration tests: the ask loop's terminal answer follows the injected port.

A real ``ConsoleAskLoop`` runs against a port double. Presence is authoritative
from the port, so the loop agrees with the lifecycle manager; stdin itself must
also be a terminal before prompt_toolkit is used, because prompt_toolkit and
``termios`` cannot drive a pipe. A piped run therefore always reads its answer
through ``input()``.
"""

import io
import sys
from typing import cast

import teddy_executor.adapters.outbound.console_interactor_ask_loop as ask_loop_module
from teddy_executor.adapters.outbound.console_interactor_ask_loop import (
    ConsoleAskLoop,
)
from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper


class FakeSystemEnvironment:
    """Presence double whose answer the test can flip."""

    def __init__(self, isatty: bool) -> None:
        self.isatty_value = isatty

    def isatty(self) -> bool:
        return self.isatty_value


class TtyStdin(io.StringIO):
    """A text buffer that claims to be a terminal."""

    def isatty(self) -> bool:
        return True


class PipeStdin(io.StringIO):
    """A text buffer that reports a pipe, as a test runner supplies."""

    def isatty(self) -> bool:
        return False


def _build_loop(port: FakeSystemEnvironment) -> ConsoleAskLoop:
    return ConsoleAskLoop(port, cast(ConsoleToolingHelper, None))


def test_presence_follows_the_injected_port_not_stdin(monkeypatch):
    """A port reporting no terminal answers False even when stdin is a TTY."""
    port = FakeSystemEnvironment(isatty=False)
    monkeypatch.setattr(sys, "stdin", TtyStdin(""))
    loop = _build_loop(port)

    assert loop._is_tty() is False

    port.isatty_value = True
    assert loop._is_tty() is True


def test_prompt_reads_the_pipe_instead_of_opening_prompt_toolkit(monkeypatch):
    """A port double claiming a terminal must not drive prompt_toolkit on a pipe."""
    port = FakeSystemEnvironment(isatty=True)
    monkeypatch.setattr(sys, "stdin", PipeStdin("hello\n"))
    prompted = []
    monkeypatch.setattr(
        ask_loop_module,
        "ptk_prompt",
        lambda *args, **kwargs: prompted.append(args) or "unexpected-ptk",
    )
    loop = _build_loop(port)

    assert loop._pt_prompt("What say you? ") == "hello"
    assert prompted == []


def test_prompt_keeps_prompt_toolkit_on_a_real_terminal(monkeypatch):
    """The terminal path still routes through prompt_toolkit."""
    port = FakeSystemEnvironment(isatty=True)
    monkeypatch.setattr(sys, "stdin", TtyStdin(""))
    monkeypatch.setattr(ask_loop_module, "ptk_prompt", lambda *a, **k: "from-ptk")
    loop = _build_loop(port)

    assert loop._pt_prompt("What say you? ") == "from-ptk"
