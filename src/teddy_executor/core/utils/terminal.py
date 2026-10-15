"""Shared terminal-mode helpers.

Single source of truth for restoring the terminal's cooked mode after an
external editor exits in raw mode (Bug 56). Historically this concern was
duplicated across >=3 adapter sites, two of which silently forgot to re-enable
``ISIG | IEXTEN`` and so left the terminal unable to GENERATE SIGINT on Ctrl+C.
"""

import logging
import os
import sys

import typer

logger = logging.getLogger(__name__)


def emit_user_message(content: str) -> None:
    """Echo a user's message to the terminal under the "User Message:" label.

    The single source of truth for the terminal-echo format, shared by the
    initial-request echo, the post-execution user-message echo, and the
    injected ``resume -m`` echo. Renders a blank separator, the
    "User Message:" label, then the stripped content. Empty or
    whitespace-only content is a no-op so an empty echo never becomes noise.
    """
    if not content or not content.strip():
        return
    typer.secho("")
    typer.secho("User Message:")
    typer.secho(content.strip())


def restore_cooked_mode() -> None:
    """Restore the terminal's cooked mode (Unix only; no-op elsewhere).

    Re-enables ``ICRNL`` (input CR->NL translation) plus
    ``ICANON | ECHO | ISIG | IEXTEN`` so the terminal keeps canonical line
    editing, echoing, extended input processing, AND keeps GENERATING SIGINT on
    Ctrl+C (a child editor such as vim/nvim may exit with these cleared).

    No-op when not on a real TTY and under the test harness / Windows, so it is
    safe to call unconditionally from a subprocess ``finally`` block.
    """
    if (
        sys.platform == "win32"
        or "PYTEST_CURRENT_TEST" in os.environ
        or not sys.stdin.isatty()
    ):
        return

    try:
        import termios  # noqa: PLC0415

        fd = sys.stdin.fileno()
        attrs = termios.tcgetattr(fd)
        # iflags: ensure ICRNL (map CR to NL on input).
        attrs[0] |= termios.ICRNL
        # lflags: re-enable cooked mode -- canonical, echo, signal generation,
        # and extended processing.
        attrs[3] |= termios.ICANON | termios.ECHO | termios.ISIG | termios.IEXTEN
        # Apply and FLUSH the input buffer.
        termios.tcsetattr(fd, termios.TCSAFLUSH, attrs)
    except Exception as e:
        logger.debug("Failed to restore terminal cooked mode: %s", e)
