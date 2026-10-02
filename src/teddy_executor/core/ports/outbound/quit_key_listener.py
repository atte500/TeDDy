"""Outbound port: an environment-agnostic terminal single-key quit listener.

Some terminals never deliver a Ctrl+C byte to the application (Bug 56), so a
quit trigger that depends only on an ordinary character key is required. This
port abstracts the lifecycle and the trigger hook of such a listener, letting
the session-loop boundary start/stop it and observe a quit without coupling to
a concrete TTY reader.
"""

from typing import Callable, Protocol, runtime_checkable

# The trigger hook a concrete reader invokes when the quit key is pressed.
# Constructor-Injected into the implementation so the port stays behavior-free.
QuitCallback = Callable[[], None]


@runtime_checkable
class IQuitKeyListener(Protocol):
    """A terminal single-key quit listener with a start()/stop() lifecycle.

    Implementations observe a single quit key on the controlling terminal while
    ``start()``ed and invoke the injected ``on_quit`` callback when it is
    pressed. The lifecycle is idempotent and a no-op when stdin is not a TTY.
    """

    def start(self) -> None:
        """Begin listening for the quit key."""
        ...

    def stop(self) -> None:
        """Stop listening and release any acquired terminal state."""
        ...
