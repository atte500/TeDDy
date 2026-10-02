"""FakeQuitKeyListener: in-memory IQuitKeyListener conformance double.

The real terminal quit-key reader drives a TTY and is an explicit no-op
off-TTY (Bug 56), so its ``start()``/``stop()`` lifecycle is unobservable in
an in-process test. This hand-rolled double records the lifecycle and exposes
a ``fire_quit()`` hook that triggers the Constructor-Injected ``on_quit``
callback, letting the Wiring boundary test observe the listener lifecycle
without a real TTY.

Anti-mock-poisoning: a plain class with constructor-set state (not a dynamic
mock), mirroring ``FakeHTTPResponse`` / ``FakeRegistryCache``.
"""

from __future__ import annotations

from typing import Optional

from teddy_executor.core.ports.outbound.quit_key_listener import QuitCallback


class FakeQuitKeyListener:
    """In-memory IQuitKeyListener conformance double.

    Records ``start()``/``stop()`` invocations in ``lifecycle`` and, via
    ``fire_quit()``, invokes the Constructor-Injected ``on_quit`` callback so a
    boundary test can simulate the user pressing the quit key.
    """

    def __init__(self, on_quit: Optional[QuitCallback] = None) -> None:
        self._on_quit = on_quit
        self.lifecycle: list[str] = []

    def start(self) -> None:
        """Record that listening has begun."""
        self.lifecycle.append("start")

    def stop(self) -> None:
        """Record that listening has stopped."""
        self.lifecycle.append("stop")

    def fire_quit(self) -> None:
        """Simulate the quit-key press by invoking the injected callback.

        A no-op when no callback was injected; never mutates ``lifecycle``.
        """
        if self._on_quit is not None:
            self._on_quit()
