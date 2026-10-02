"""ContainerStub: in-memory punq-compatible container conformance double.

The session-loop wiring suites (interrupt wiring, quit-listener wiring) and the
resume-message threading suite each carried a hand-rolled, byte-identical
``_ContainerStub``. This shared stub retires all three copies: a ``resolve``-
compatible double that returns the mapped service for a known type and a bare
``Mock()`` fallback for unmapped types.

Anti-mock-poisoning: a plain class with constructor-set state (not a dynamic
mock), mirroring ``FakeHTTPResponse`` / ``FakeRegistryCache`` /
``FakeQuitKeyListener``.
"""

from __future__ import annotations

from unittest.mock import Mock


class ContainerStub:
    """Hand-rolled punq-compatible container double (no bare MagicMock)."""

    def __init__(self, mapping: dict[type, object]) -> None:
        self._mapping = mapping

    def resolve(self, service_type: type, **kwargs: object) -> object:
        service = self._mapping.get(service_type)
        if service is None:
            return Mock()
        return service
