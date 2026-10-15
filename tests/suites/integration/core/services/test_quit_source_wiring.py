"""Integration tests: composition-root quit-source wiring (Slice 00-37, Harness).

The bare-``q`` quit-key listener and the session-loop boundary share ONE
process-global ``InterruptGuard``. The composition root binds the listener's
``on_quit`` callback to ``_record_quit_source``, which records ``"q"`` on that
shared guard BEFORE self-delivering SIGINT -- so the interrupt notice can name
the key the user actually pressed instead of defaulting to ``Ctrl+C``.

This suite pins that seam against the REAL container: driving the wired
listener's quit hook must record ``q`` on the SAME guard the boundary resolves,
and the notice composed from that guard must name ``q``. ``os.kill`` is stubbed
so the test observes the recording half of the seam without raising
KeyboardInterrupt.
"""

import os

from teddy_executor.core.ports.outbound.quit_key_listener import IQuitKeyListener
from teddy_executor.core.utils.interrupt_guard import InterruptGuard
from teddy_executor.core.utils.session_notices import format_interrupt_notice


def test_pressing_the_quit_key_records_q_on_the_shared_guard(container, monkeypatch):
    """Pressing `q` through the wired listener names `q` on the shared guard."""
    # Arrange: the recorder self-delivers SIGINT AFTER recording, so stub
    # os.kill to observe the recording without interrupting the test process.
    monkeypatch.setattr(os, "kill", lambda *args, **kwargs: None)
    guard = container.resolve(InterruptGuard)
    listener = container.resolve(IQuitKeyListener)

    # Act: simulate the user pressing `q` (the wired on_quit hook fires).
    listener._trigger()

    # Assert: the shared guard names the pressed key, and the notice built from
    # that guard names `q` (not the Ctrl+C default).
    assert guard.source == "q"
    assert format_interrupt_notice(guard.source) == (
        "Interrupted by user (q). To continue the session, use `teddy resume`."
    )
