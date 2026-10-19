"""Integration tests: composition-root quit-source wiring (Slice 00-37, Harness).

The bare-``q`` quit-key listener and the session-loop boundary share ONE
process-global ``InterruptGuard``. The composition root binds the listener's
``on_quit`` callback to ``_record_quit_source``, which records ``"q"`` on that
shared guard BEFORE self-delivering SIGINT -- so the interrupt notice can name
the key the user actually pressed instead of defaulting to ``Ctrl+C``.

This suite pins that seam against the REAL container: driving the wired
listener's quit hook must record ``q`` on the SAME guard the boundary resolves,
and the notice composed from that guard must name ``q``. The SIGINT delivery
primitive is stubbed so the test observes the recording half of the seam
without raising KeyboardInterrupt.
"""

import signal

from teddy_executor.core.ports.outbound.quit_key_listener import IQuitKeyListener
from teddy_executor.core.utils.interrupt_guard import InterruptGuard
from teddy_executor.core.utils.session_notices import format_interrupt_notice


def test_pressing_the_quit_key_records_q_on_the_shared_guard(container, monkeypatch):
    """Pressing `q` through the wired listener names `q` on the shared guard."""
    # Arrange: the recorder self-delivers SIGINT AFTER recording. Stub the
    # shared primitive so the seam is observable without interrupting the test
    # process.
    delivered = []
    monkeypatch.setattr(signal, "raise_signal", lambda sig: delivered.append(sig))
    guard = container.resolve(InterruptGuard)
    listener = container.resolve(IQuitKeyListener)

    # Act: simulate the user pressing `q` (the wired on_quit hook fires).
    listener._trigger()

    # Assert: the shared guard names the pressed key, delivery reached the
    # shared primitive, and the notice built from that guard names `q` (not the
    # Ctrl+C default).
    assert guard.source == "q"
    assert delivered == [signal.SIGINT]
    assert format_interrupt_notice(guard.source) == (
        "Interrupted by user (q). To continue the session, use `teddy resume`."
    )
