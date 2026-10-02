"""Seam tests: the composition root provides a process-global terminal
quit-key listener (Bug 56 bare-`q`).

The session-loop boundary needs an ``IQuitKeyListener`` it can start/stop
around the turn loop. This Seam provides the concrete
``TerminalQuitKeyListener`` from the composition root as a
``punq.Scope.singleton`` (ONE process-global instance, mirroring the
``InterruptGuard`` boundary/ports identity precedent) so a single listener
drives the shared two-phase interrupt semantics. The reader internals
(non-canonical TTY mode save/restore, byte detection, prompt-pause) belong to
the downstream Logic deliverable; this suite pins only that the container
resolves the port to a real listener and that the instance is a process-global
singleton.
"""

from teddy_executor.adapters.outbound.terminal_quit_key_listener import (
    TerminalQuitKeyListener,
)
from teddy_executor.core.ports.outbound.quit_key_listener import IQuitKeyListener


def test_container_provides_a_terminal_quit_key_listener(container):
    """The composition root resolves the port to a real concrete listener."""
    listener = container.resolve(IQuitKeyListener)

    assert isinstance(listener, TerminalQuitKeyListener)


def test_container_quit_key_listener_is_a_process_global_singleton(container):
    """ONE process-global instance drives the SAME two-phase semantics."""
    assert container.resolve(IQuitKeyListener) is container.resolve(IQuitKeyListener)
