"""Wiring tracer: a terminal routes the Message body through the renderer."""

import io

from rich.console import Console

from teddy_executor.core.services.session_orchestrator import (
    _print_message_from_teddy,
)

BODY = "Run `teddy resume -p` to continue.\n"


def _recording_console(*, terminal: bool) -> tuple[Console, io.StringIO]:
    buffer = io.StringIO()
    return Console(file=buffer, width=80, force_terminal=terminal), buffer


def test_terminal_console_routes_body_through_renderer(capsys):
    """On a terminal the framing goes to typer and the body to the renderer."""
    console, buffer = _recording_console(terminal=True)

    _print_message_from_teddy(BODY, console=console)

    out = capsys.readouterr().out
    assert "--- MESSAGE from TeDDy ---" in out
    assert BODY.rstrip("\n") in buffer.getvalue()


def test_non_terminal_console_emits_raw_body(capsys):
    """Off a terminal the body is emitted raw through typer, as today."""
    console, buffer = _recording_console(terminal=False)

    _print_message_from_teddy(BODY, console=console)

    out = capsys.readouterr().out
    assert "--- MESSAGE from TeDDy ---" in out
    assert BODY.rstrip("\n") in out
    assert buffer.getvalue() == ""
