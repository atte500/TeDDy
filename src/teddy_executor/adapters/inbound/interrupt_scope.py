"""The shared interrupt bracket both inbound boundaries need.

One owner installs the SIGINT disposition and starts the quit-key listener for
the block it wraps, then releases both in ``finally`` on every exit path. Two
owners cannot each take their own snapshot, because they would restore each
other's handler; that is why the session loop and the stateless ``execute``
run both enter through this single seam.

The seam owns only the lifecycle. It never swallows an interrupt or an exit
code: the boundary that entered the bracket owns the notice and the status.
"""

from contextlib import contextmanager
from typing import Iterator

from teddy_executor.core.ports.outbound.quit_key_listener import IQuitKeyListener
from teddy_executor.core.utils.interrupt_guard import InterruptGuard


@contextmanager
def interrupt_scope(
    guard: InterruptGuard, listener: IQuitKeyListener
) -> Iterator[InterruptGuard]:
    """Brackets a run: install the guard, start the listener, then release both.

    Transient press state is cleared on entry, because one memoized container
    keeps a single guard alive across in-process commands and a stale source
    would name the previous run's key in this run's notice. The listener starts
    inside the guard's claim window so a raising start cannot orphan the claim,
    and it stops before the disposition is restored so no keystroke is read
    while the previous handler comes back.
    """
    guard.clear_source()
    guard.install()
    try:
        listener.start()
        yield guard
    finally:
        listener.stop()
        guard.restore()
