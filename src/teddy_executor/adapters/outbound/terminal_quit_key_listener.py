"""Concrete terminal single-key quit listener (Bug 56 bare-`q`).

An environment-agnostic ``IQuitKeyListener`` for terminals that never deliver
a Ctrl+C byte: when the quit key is pressed the listener invokes its
Constructor-Injected ``on_quit`` callback, which self-delivers SIGINT so the
shared ``InterruptGuard`` runs its already-tested WAITING/EXECUTING branch
unchanged.

This Seam deliverable establishes the adapter and its composition-root
registration only; the reader internals (non-canonical TTY mode save/restore,
byte detection, prompt-pause, and the production ``on_quit`` self-delivery)
belong to the downstream Logic reader deliverable.
"""

from __future__ import annotations

from typing import Optional

from teddy_executor.core.ports.outbound.quit_key_listener import QuitCallback


class TerminalQuitKeyListener:
    """Concrete IQuitKeyListener supplied as a process-global singleton.

    Constructor-Injected ``on_quit`` is the trigger hook invoked when the quit
    key is pressed; it defaults to None so the composition root can construct
    the listener before the reader mechanics land.
    """

    def __init__(self, on_quit: Optional[QuitCallback] = None) -> None:
        self._on_quit = on_quit

    def start(self) -> None:
        """Begin listening for the quit key."""

    def stop(self) -> None:
        """Stop listening and release any acquired terminal state."""
