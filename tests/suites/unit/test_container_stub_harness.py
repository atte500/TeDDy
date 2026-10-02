"""Harness tests: the shared punq-compatible container stub.

The session-loop wiring suites each carried a hand-rolled, byte-identical
``_ContainerStub`` (interrupt wiring, quit-listener wiring, resume-message
threading). The shared ``ContainerStub`` retires all three copies: a punq
``resolve``-compatible double that returns the mapped service for a known type
and a bare ``Mock()`` fallback for unmapped types.

Mirrors the established harness-double convention (``FakeHTTPResponse``,
``FakeRegistryCache``, ``FakeQuitKeyListener``): a plain class with
constructor-set state.
"""

from unittest.mock import Mock

from tests.harness.setup.container_stub import ContainerStub


def test_resolves_a_mapped_type_to_the_exact_service():
    """A mapped type must resolve to the EXACT service instance injected."""
    mapped = object()
    stub = ContainerStub({int: mapped})

    assert stub.resolve(int) is mapped


def test_returns_a_mock_fallback_for_an_unmapped_type():
    """An unmapped type must fall back to a bare Mock() instance."""
    stub = ContainerStub({})

    resolved = stub.resolve(str)

    assert isinstance(resolved, Mock)
